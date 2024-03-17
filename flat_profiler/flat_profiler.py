import functools
import logging
import time
from collections import defaultdict
from collections.abc import Callable, Generator
from operator import itemgetter
from typing import ParamSpec, Protocol, TypeAlias, TypeVar

from recompyle.rewrite import CallExtras, rewrite_wrap_calls_func

P = ParamSpec("P")
T = TypeVar("T")
TimeDict: TypeAlias = dict[tuple[tuple[int, ...], str, str], list[float]]


class ProfilerCallback(Protocol):
    """Profiler callback protocol."""

    def __call__(self, total: float, limit: float, times: TimeDict, func: Callable) -> None:
        """Callback to run after the function transformed with flat_profile is executed.

        Args:
            total (float): Total execution time of the function.
            limit (float): Time limit configured for the function.
            times (TimeDict): All calls recorded and their execution times. Keys are the call names, while
                the value is a list of each execution time in the order the calls occurred.
            func (Callable): The function the calls were within.
        """


def collect_profiling_lines(times: TimeDict) -> Generator[str, None, None]:
    """Convert call data to readable profiling lines.

    For each call, the first line includes:
    - The call as it appears in the original source.
    - The __qualname__ or __name__ of the call.
    - The source line number the call was on.
    """
    calc_times = ((func_key, (s := sum(times)), (ln := len(times)), s / ln) for func_key, times in times.items())
    return (
        (
            f"{func_key[1]} | {func_key[2]} | L{'-'.join(str(f) for f in func_key[0])}\n"
            f"  ↪ {ttl_time:.3g}s total, {avg_time:.3g}s avg, {calls} calls"
        )
        for func_key, ttl_time, calls, avg_time in sorted(calc_times, key=itemgetter(1), reverse=True)
    )


def default_above_log(total: float, limit: float, times: TimeDict, func: Callable) -> None:
    """Log total time and detailed call details."""
    log = logging.getLogger(func.__module__)
    detailstr = "\n".join(collect_profiling_lines(times))
    log.warning(f"{func.__qualname__} finished in {total:.3g}s, above limit of {limit:.3g}s\n" + detailstr)


def default_below_log(total: float, limit: float, times: TimeDict, func: Callable) -> None:
    """Log total time without call details."""
    log = logging.getLogger(func.__module__)
    log_str = f"{func.__qualname__} finished in {total:.3g}s, below limit of {limit:.3g}s"
    log.info(log_str)


def _find_name(call: Callable) -> str:
    """Get name of a given callable."""
    try:
        return call.__qualname__
    except AttributeError:
        pass

    try:
        return call.__name__
    except AttributeError:
        pass

    try:
        return _find_name(call.__wrapped__)
    except AttributeError:
        return type(call).__name__


def flat_profile(
    *,
    time_limit: float,
    below_callback: ProfilerCallback | None = default_below_log,
    above_callback: ProfilerCallback | None = default_above_log,
    ignore_builtins: bool = True,
    blacklist: set[str] | None = None,
    whitelist: set[str] | None = None,
    rewrite_details: dict | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Rewrites target function to record runtime of each call in it.

    A time limit must be provided, where one of two callback functions will be run depending on whether the total
    execution time of the function is below (exclusive) or above (inclusive) of the decorated function. By default
    simple INFO-level logging functions are provided that will report only the total function time if that total is
    below the time limit, and if above it will also log the sum of times for each call.

    Call times are recorded to a dictionary that is local to the decorated function. Keys are the name of calls, and the
    values are lists of execution times. This list is cleared after each execution. You can access this dictionary by
    providing alternative callbacks.

    Callback parameters include total execution time, time limit, the callable time dictionary, and a reference to the
    decorated function.

    Args:
        time_limit (float): Threshold that determines which callback run after decorated function runs.
        below_callback (ProfilerCallback | None): Called when execution time is under the time limit.
        above_callback (ProfilerCallback | None): Called when execution time is equal to or over the time limit.
        ignore_builtins (bool): Whether to skip wrapping builtin calls. Must be False to use whitelist. Default True.
        blacklist (set[str] | None): Call names that should not be wrapped. String literal subscripts should not use
            quotes, e.g. use a name of `"a[b]"` to match code written as `a["b"]()`. Subscripts can be wildcards using an
            asterisk, like `"a[*]"` which would match all of `a[0]()` and `a[val]()` and `a["key"]()` etc.
        whitelist (set[str] | None): Call names that should be wrapped. Allows wildcards like blacklist.
        rewrite_details (dict | None): If provided the given dict will be updated to store the original function object
            and original/new source in the keys `original_func`, `original_source`, and `new_source`.

    Returns:
        Callable: A decorator that will replace the wrapped function.
    """
    if below_callback is None and above_callback is None:
        raise ValueError("At least one of before_callback and above_callback must be non-None")

    _call_times: defaultdict[tuple[tuple[int, ...], str, str], list[float]] = defaultdict(list)
    _call_names: dict[object, str] = {}

    def _get_name(call: Callable) -> str:
        """Use stored callable name or find if the callable is new."""
        try:
            return _call_names[call]
        except KeyError:
            pass

        _call_names[call] = _find_name(call)
        return _call_names[call]

    def _record_call_time(__call: Callable[P, T], __extras: CallExtras, *args: P.args, **kwargs: P.kwargs) -> T:
        """Wrapper to record execution time of inner calls."""
        start = time.perf_counter()
        try:
            return __call(*args, **kwargs)
        finally:
            end = time.perf_counter()
            _call_times[(__extras["ln_range"], __extras["source"], _get_name(__call))].append(end - start)

    def _measure_calls(func: Callable[P, T]) -> Callable[P, T]:
        """Decorator to measure total call time and inner call times."""
        _new_func = rewrite_wrap_calls_func(
            target_func=func,
            wrapper=_record_call_time,
            ignore_builtins=ignore_builtins,
            blacklist=blacklist,
            whitelist=whitelist,
            rewrite_details=rewrite_details,
        )

        @functools.wraps(func)
        def inner_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start = time.perf_counter()
            try:
                return _new_func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                if below_callback is not None and duration < time_limit:
                    below_callback(duration, time_limit, _call_times.copy(), _new_func)
                elif above_callback is not None and duration >= time_limit:
                    above_callback(duration, time_limit, _call_times.copy(), _new_func)
                _call_times.clear()

        return inner_wrapper

    return _measure_calls
