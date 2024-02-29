# Flat Profiler

This package provides a flat profiler, which collects execution time information for only the decorated function or method.


# Installation

`pip install flat_profile`


# Usage

This decorator uses call wrapping from [Recompyle](https://github.com/DanWehr/recompyle) to record the execution times of all calls, of the decorated function. A time limit must be provided, and if the total time is below/above that limit then below/above callbacks will execute.

The default `below` callback will create a log message with only the total time. The default `above` callback will log the total as well as all call execution times, sorted by highest duration first.

Multiple call times for the same name (e.g. from multiple `int()` calls) will be summed together for the default logging. Custom callbacks used instead of the default ones will receive the times of all individual calls.

```python
import logging
import time

from flat_profiler import flat_profile

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def slow_function(val: float) -> str:
    """Slow function being called."""
    time.sleep(0.5)  # Force total time of example_function over limit
    return f"other val: {val}"


def faster_function() -> None:
    """Faster function being called."""
    time.sleep(0.001)


@flat_profile(time_limit=0.3)
def example_function(count: int) -> str:
    """Function we are rewriting to time calls."""
    faster_function()
    for _ in (int(v) for v in range(count)):
        pass
    return slow_function(val=123.45)


log.info(example_function(2))
```

This will produce the following log output:

```text
INFO:flat_profiler.flat_profiler:example_function finished in 0.5115s, above limit of 0.3s
('slow_function: 0.508s',
 'faster_function: 0.00294s',
 'int: 2.4e-06s',
 'range: 8e-07s')
INFO:__main__:other val: 123.45
```

Only the `time_limit` parameter is required. Optional parameters are available to replace the default callbacks, as well as many others for further configuration:

- `time_limit` (float): Threshold that determines which callback run after decorated function runs.
- `below_callback` (Callable | None): Called when execution time is under the time limit.
- `above_callback` (Callable | None): Called when execution time is equal to or over the time limit.
- `ignore_builtins` (bool): Whether to skip wrapping builtin calls.
- `blacklist` (set[str] | None): Call names that should not be wrapped. String literal subscripts should not use quotes, e.g. use a name of `"a[b]"` to match code written as `a["b"]()`. Subscripts can be wildcards using an asterisk, like `"a[*]"` which would match all of `a[0]()` and `a[val]()` and `a["key"]()` etc.
- `whitelist` (set[str] | None): Call names that should be wrapped. Allows wildcards like blacklist.
- `rewrite_details` (dict | None): If provided the given dict will be updated to store the original function object and original/new source in the keys `original_func`, `original_source`, and `new_source`.

See [ProfilerCallback](flat_profiler/flat_profiler.py) for details on the callback arguments.


# Performance

Performance has been measured using a [script](flat_profiler/performance.py) with multiple versions of a simple function with 10 calls, one of which is undecorated to serve as a baseline reference to contrast with the `flat_profile` decorated version. The numbers below are from running this script on an i7-6700K CPU, running Windows 10.

```text
Running unwrapped function 100,000 times, repeat 100/100: average 0.7506689800004096 microseconds
Running flat profiler w/ no callback 10,000 times, repeat 100/100: average 6.848101899999165 microseconds
Running flat profiler w/ default below callback 10,000 times, repeat 100/100: average 8.47701797000118 microseconds
Running flat profiler w/ default above callback 10,000 times, repeat 100/100: average 16.656903400000374 microseconds

Flat profiler call cost is 0.6097432919998755 microseconds per wrapped call
Flat profiler default below callback costs 1.628916070002015 microseconds
Flat profiler default above callback costs 9.80880150000121 microseconds
```

With these numbers if you applied the flat profiler to a function with 100 calls that are wrapped, used the default logging callbacks, and total function runtime was generally below the profiler time limit (the "below" callback is triggered), then the flat profiler would add a total of only (100 * 0.609743) + 1.628916 = 62.603216 μs to the execution time of the function. When the execution time is high enough to trigger the more costly "above" default callback (which processes and sorts call times to include them in its log message) this cost increases to (100 * 0.609743) + 9.808802 = 70.783102 μs.

While this performance will differ across devices, with results of a small fraction of a millisecond this indicates the performance impact should typically be insignificant. This meets the original goal of being able to continuously monitor a function in a production system, especially if it is run infrequently such as once a second or less often. Note that this analysis only applies to the default below/above callbacks included in this project, and custom callbacks could have significantly different performance.

To check performance on other devices, you can run this performance script yourself with the command `python -m flat_profiler.performance`.


# Background

This project came from the need to monitor execution time of a function in a production system, and if an abnormal (above a threshold) execution time was encountered, to provide more detail than a simple decorator that just records the execution time of the entire function. Knowing *what* in the function was responsible for the time increase could help significantly with debugging/optimizing.

A full call stack would be the most useful which you can get through tools like the builtin cProfile, but there is typically enough overhead that it is not feasible for use in production. One way to address that overhead would be to only periodically profile the program (such as in statistical profiling), but that is primarily useful for monitoring your average execution behavior. If you want to profile abnormal cases like a slowdown that happens rarely (such as once a day), you need to be able to monitor the relevant code continuously to guarantee that rare event is captured. For this to be possible the overhead must be very low, and one way to achieve this is to limit the scope of that profiling to only a small piece of the program.

The profiler implemented here is "flat" because it captures the execution times of *all* calls within a decorated function, and *only* the calls within that function. It does not analyze the contents of any of those inner calls, nor any parent function that called the decorated one.


# Contributing

Bugs, feedback and requests should all be handled through this project's [GitHub Issues](https://github.com/DanWehr/flat_profiler/issues) page.
