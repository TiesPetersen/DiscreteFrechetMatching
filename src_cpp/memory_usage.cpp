#include "common.h"
#include "bbms_inter.h"
#include "generate_adversarial.h"
#include <chrono>
#include <iostream>
#include <string>
#include <sys/resource.h>

// Delta between two getrusage() snapshots, isolating the resource cost of
// whatever ran between them (here: bbms_inter's call, not curve generation).
struct RUsageDelta {
    double   user_time_s;
    double   sys_time_s;
    long long minor_faults;  // satisfied from memory already resident (cheap)
    long long major_faults;  // required real I/O, e.g. disk/compressor (the signal we care about)
    long long swaps;         // legacy whole-process swap counter; usually 0 on modern macOS
    long long block_input_ops;
    long long block_output_ops;
    long long voluntary_ctx_switches;
    long long involuntary_ctx_switches;  // spikes when a fault blocks the process on I/O
};

static double timeval_to_s(const struct timeval& tv) {
    return (double)tv.tv_sec + (double)tv.tv_usec / 1e6;
}

static RUsageDelta diff_rusage(const struct rusage& before, const struct rusage& after) {
    return {
        timeval_to_s(after.ru_utime) - timeval_to_s(before.ru_utime),
        timeval_to_s(after.ru_stime) - timeval_to_s(before.ru_stime),
        after.ru_minflt  - before.ru_minflt,
        after.ru_majflt  - before.ru_majflt,
        after.ru_nswap   - before.ru_nswap,
        after.ru_inblock - before.ru_inblock,
        after.ru_oublock - before.ru_oublock,
        after.ru_nvcsw   - before.ru_nvcsw,
        after.ru_nivcsw  - before.ru_nivcsw,
    };
}

int main(int argc, char* argv[]) {
    if (argc != 3) {
        std::cerr << "usage: memory_usage.exe <N> <sample>\n";
        return 1;
    }

    int N      = std::stoi(argv[1]);
    int sample = std::stoi(argv[2]);

    // Same seed formula used elsewhere in this project for reproducibility.
    unsigned seed = (unsigned)(sample * 9999 + N);
    auto [p, q] = generate_adversarial_pair(N, 1.0, 1000.0, seed);

    double runtime_s = -1.0, frechet = -1.0;
    RUsageDelta delta{};
    long before_maxrss = 0, after_maxrss = 0;
    bool ok = false;

    try {
        // Snapshot immediately before/after the call under test, so curve
        // generation's own allocations don't pollute the fault/CPU-time deltas.
        struct rusage before{}, after{};
        getrusage(RUSAGE_SELF, &before);

        auto t0 = std::chrono::high_resolution_clock::now();
        auto [matching, fd] = bbms_inter(p, q);
        auto t1 = std::chrono::high_resolution_clock::now();

        getrusage(RUSAGE_SELF, &after);

        runtime_s = std::chrono::duration<double>(t1 - t0).count();
        frechet   = fd;
        delta     = diff_rusage(before, after);

        // ru_maxrss is a whole-process high-water mark, not a delta — it can only
        // grow. Reporting both endpoints shows how much of the peak is attributable
        // to this call vs. setup (curve generation is O(N), negligible next to the
        // O(N^2) node grid bbms_inter allocates, so the gap is essentially the run).
        // NOTE: macOS reports ru_maxrss in bytes; Linux reports it in kilobytes.
        before_maxrss = before.ru_maxrss;
        after_maxrss  = after.ru_maxrss;

        ok = true;
    } catch (const std::bad_alloc&) {
        // OOM before swap could even help — falls through with ok=false
    } catch (...) {
    }

    double before_rss_mb = before_maxrss / (1024.0 * 1024.0);
    double after_rss_mb  = after_maxrss  / (1024.0 * 1024.0);

    std::cout << N << "," << sample << ","
              << runtime_s << "," << frechet << ","
              << before_rss_mb << "," << after_rss_mb << ","
              << delta.minor_faults << "," << delta.major_faults << ","
              << delta.swaps << ","
              << delta.block_input_ops << "," << delta.block_output_ops << ","
              << delta.voluntary_ctx_switches << "," << delta.involuntary_ctx_switches << ","
              << delta.user_time_s << "," << delta.sys_time_s << ","
              << (ok ? "True" : "False") << "\n";
    return 0;
}
