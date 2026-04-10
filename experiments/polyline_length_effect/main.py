from polyline_datasets.generate_polylines import generate_random_polylines

from src.BBMS.main import BBMS
from src.BBMS_core.main import BBMS_core
from src.DijkstraPrims.main import DijkstraPrims

import time
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats


# Parameters for the experiment
startingLength = 250
endingLength = 5000
step = 250
max_num_polylines = 20  # Number of cumulative iterations (one pair per length per iteration)


def run_benchmark(polyline_a, polyline_b, algorithm):
    """Runs one algorithm call on one pair and returns runtime in seconds."""
    try:
        start = time.perf_counter()

        if algorithm == 'bbms':
            BBMS(polyline_a, polyline_b)
        elif algorithm == 'bbms_core':
            BBMS_core(polyline_a, polyline_b)
        elif algorithm == 'dijkstraprims':
            DijkstraPrims(polyline_a, polyline_b)
        else:
            print(f"Unknown algorithm: {algorithm}")
            return None

        end = time.perf_counter()
        return end - start

    except Exception as e:
        print(f"Error running {algorithm}: {e}")
        return None


def summarize_times(times):
    """Returns mean runtime and 95% CI half-width for a list of runtimes."""
    mean_time = float(np.mean(times))
    if len(times) < 2:
        return (mean_time, 0.0)

    std_error = stats.sem(times)
    ci_half_width = float(std_error * stats.t.ppf(0.975, len(times) - 1))
    return (mean_time, ci_half_width)


def plotResults(results, iteration):
    lengths = list(results.keys())
    bbms_times = [results[length]['bbms'][0] for length in lengths]
    bbms_ci = [results[length]['bbms'][1] for length in lengths]
    # bbms_core_times = [results[length]['bbms_core'][0] for length in lengths]
    # bbms_core_ci = [results[length]['bbms_core'][1] for length in lengths]
    dijkstraprims_times = [results[length]['dijkstraprims'][0] for length in lengths]
    dijkstraprims_ci = [results[length]['dijkstraprims'][1] for length in lengths]

    plt.figure(figsize=(10, 6), dpi=300)
    
    # Plot BBMS with confidence interval shading
    plt.plot(lengths, bbms_times, label='BBMS', marker='o', linewidth=2, color='tab:blue')
    plt.fill_between(lengths, 
                      [t - ci for t, ci in zip(bbms_times, bbms_ci)],
                      [t + ci for t, ci in zip(bbms_times, bbms_ci)],
                      alpha=0.2, label='95% CI', color='tab:blue')
    
    # Plot BBMS Core with confidence interval shading
    # plt.plot(lengths, bbms_core_times, label='BBMS Core', marker='o', linewidth=2, color='tab:orange')
    # plt.fill_between(lengths,
    #                   [t - ci for t, ci in zip(bbms_core_times, bbms_core_ci)],
    #                   [t + ci for t, ci in zip(bbms_core_times, bbms_core_ci)],
    #                   alpha=0.2, label='95% CI', color='tab:orange')
    
    # Plot DijkstraPrims with confidence interval shading
    plt.plot(lengths, dijkstraprims_times, label='DijkstraPrims', marker='o', linewidth=2, color='tab:green')
    plt.fill_between(lengths,
                      [t - ci for t, ci in zip(dijkstraprims_times, dijkstraprims_ci)],
                      [t + ci for t, ci in zip(dijkstraprims_times, dijkstraprims_ci)],
                      alpha=0.2, label='95% CI', color='tab:green')
    
    
    # y axis should start at 0, but with some padding to make the plot look better
    plt.ylim(bottom=0)

    plt.xlabel('Polyline Length')
    plt.ylabel('Mean Runtime (seconds)')
    plt.title('Polyline Length vs Runtime')
    plt.tight_layout()
    plt.legend()
    plt.grid()
    plt.savefig(f'polyline_length_effect_{iteration}.png', dpi=300)
    # plt.show()
    plt.close()


def main():
    """ Runs each algorithm on differently sized polylines to analyze the effect of polyline length on runtime. """

    # Print the parameters of the experiment
    print(f"Experiment parameters:")
    print(f"  Starting length: {startingLength}")
    print(f"  Ending length: {endingLength}")
    print(f"  Step: {step}")
    print(f"  Iterations (one pair per length each iteration): {max_num_polylines}")
    print()

    lengths = list(range(startingLength, endingLength + 1, step))

    # Store all observed runtimes across iterations.
    accumulated_times = {
        length: {
            'bbms': [],
            # 'bbms_core': [],
            'dijkstraprims': []
        }
        for length in lengths
    }

    for iteration in range(1, max_num_polylines + 1):
        print(f"Starting iteration {iteration}/{max_num_polylines}...")
        for length in lengths:
            print(f"  Testing length {length}...")
            polylines = generate_random_polylines(
                num_polylines=2,
                length_range=(length, length),
                x_range=(0, 10),
                y_range=(0, 10)
            )

            bbms_time = run_benchmark(polylines[0], polylines[1], 'bbms')
            # bbms_core_time = run_benchmark(polylines[0], polylines[1], 'bbms_core')
            dijkstraprims_time = run_benchmark(polylines[0], polylines[1], 'dijkstraprims')

            # if bbms_time is None or bbms_core_time is None or dijkstraprims_time is None:
            #     print("Aborting entire experiment, because one or more algorithms failed.")
            #     exit(1)

            if bbms_time is None or dijkstraprims_time is None:
                print("Warning: One or more algorithms failed on this pair, skipping.")
                exit(1)

            accumulated_times[length]['bbms'].append(bbms_time)
            # accumulated_times[length]['bbms_core'].append(bbms_core_time)
            accumulated_times[length]['dijkstraprims'].append(dijkstraprims_time)

        results = {}
        for length in lengths:
            results[length] = {
                'bbms': summarize_times(accumulated_times[length]['bbms']),
                # 'bbms_core': summarize_times(accumulated_times[length]['bbms_core']),
                'dijkstraprims': summarize_times(accumulated_times[length]['dijkstraprims'])
            }

        print(f"Iteration {iteration}/{max_num_polylines} completed")
        print("Benchmark results (as table):")
        # print("| Length | BBMS (mean ± CI) | BBMS Core (mean ± CI) | DijkstraPrims (mean ± CI) |")
        # print("|--------|------------------|------------------------|---------------------------|")
        # for length, times in results.items():
        #     bbms_mean, bbms_ci = times['bbms']
        #     bbms_core_mean, bbms_core_ci = times['bbms_core']
        #     dijkstraprims_mean, dijkstraprims_ci = times['dijkstraprims']
        #     print(f"| {length} | {bbms_mean:.4f} ± {bbms_ci:.4f} | {bbms_core_mean:.4f} ± {bbms_core_ci:.4f} | {dijkstraprims_mean:.4f} ± {dijkstraprims_ci:.4f} |")

        print("| Length | BBMS (mean ± CI) | DijkstraPrims (mean ± CI) |")
        print("|--------|------------------|---------------------------|")
        for length, times in results.items():
            bbms_mean, bbms_ci = times['bbms']
            dijkstraprims_mean, dijkstraprims_ci = times['dijkstraprims']
            print(f"| {length} | {bbms_mean:.4f} ± {bbms_ci:.4f} | {dijkstraprims_mean:.4f} ± {dijkstraprims_ci:.4f} |")

        plotResults(results, iteration)
        print()


if __name__ == "__main__":
    main()