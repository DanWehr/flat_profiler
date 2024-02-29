import timeit
from statistics import mean

from flat_profiler import flat_profile


def simple_wrapper(__call, *args, **kwargs):
    return __call(*args, **kwargs)


def other(val1, val2):
    return val1 + val2


def unwrapped():
    other(0, val2=1)
    other(2, val2=3)
    other(4, val2=5)
    other(6, val2=7)
    other(8, val2=9)
    other(10, val2=11)
    other(12, val2=13)
    other(14, val2=15)
    other(16, val2=17)
    other(18, val2=19)


@flat_profile(time_limit=100, below_callback=None)
def wrapped_profiler():
    other(0, val2=1)
    other(2, val2=3)
    other(4, val2=5)
    other(6, val2=7)
    other(8, val2=9)
    other(10, val2=11)
    other(12, val2=13)
    other(14, val2=15)
    other(16, val2=17)
    other(18, val2=19)


@flat_profile(time_limit=100)  # Default below callback will always run
def wrapped_profiler_below():
    other(0, val2=1)
    other(2, val2=3)
    other(4, val2=5)
    other(6, val2=7)
    other(8, val2=9)
    other(10, val2=11)
    other(12, val2=13)
    other(14, val2=15)
    other(16, val2=17)
    other(18, val2=19)


@flat_profile(time_limit=0)  # Default above callback will always run
def wrapped_profiler_above():
    other(0, val2=1)
    other(2, val2=3)
    other(4, val2=5)
    other(6, val2=7)
    other(8, val2=9)
    other(10, val2=11)
    other(12, val2=13)
    other(14, val2=15)
    other(16, val2=17)
    other(18, val2=19)


count = 10_000
repeat = 100
calls = 10
s_to_us = 1_000_000


def collect_times(stmt, label):
    times = []
    print(f"\rRunning {label} {count:,} times, repeat 0/{repeat}", end="", flush=True)
    # Make our own loop in place of timeit.repeat. Print progress so terminal doesn't appear frozen.
    for loop in range(repeat):
        times.append(timeit.timeit(stmt, number=count, globals=globals()))
        print(f"\rRunning {label} {count:,} times, repeat {loop+1}/{repeat}", end="", flush=True)
    avg = (mean(times) / count) * s_to_us
    print(": average", avg, "microseconds")
    return avg


if __name__ == "__main__":
    base_avg_us = collect_times("unwrapped()", "unwrapped function")
    profiler_avg_us = collect_times("wrapped_profiler()", "flat profiler w/ no callback")
    profiler_below_us = collect_times("wrapped_profiler_below()", "flat profiler w/ default below callback")
    profiler_above_us = collect_times("wrapped_profiler_above()", "flat profiler w/ default above callback")

    print("\nFlat profiler call cost is", (profiler_avg_us - base_avg_us) / calls, "microseconds per wrapped call")
    print("Flat profiler default below callback costs", profiler_below_us - profiler_avg_us, "microseconds")
    print("Flat profiler default above callback costs", profiler_above_us - profiler_avg_us, "microseconds")
