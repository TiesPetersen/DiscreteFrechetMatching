from polyline_datasets.generate_polylines import generate_random_polylines

from src.BBMS.main import BBMS
from src.BBMS_basic.main import BBMS_basic
from src.DijkstraPrims.main import DijkstraPrims

import time
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats


# Parameters for the experiment
startingLength = 250
endingLength = 4000
step = 250
max_num_polylines = 20  # Number of cumulative iterations (one pair per length per iteration)


def run_benchmark(polyline_a, polyline_b, algorithm):
    """Runs one algorithm call on one pair and returns runtime in seconds."""
    try:
        start = time.perf_counter()

        if algorithm == 'bbms':
            BBMS(polyline_a, polyline_b)
        elif algorithm == 'bbms_basic':
            BBMS_basic(polyline_a, polyline_b)
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


def plotResults(results):
    lengths = list(results.keys())
    bbms_times = [results[length]['bbms'][0] for length in lengths]
    bbms_ci = [results[length]['bbms'][1] for length in lengths]
    bbms_basic_times = [results[length]['bbms_basic'][0] for length in lengths]
    bbms_basic_ci = [results[length]['bbms_basic'][1] for length in lengths]
    dijkstraprims_times = [results[length]['dijkstraprims'][0] for length in lengths]
    dijkstraprims_ci = [results[length]['dijkstraprims'][1] for length in lengths]

    plt.figure(figsize=(10, 6), dpi=300)
    
    # Plot BBMS with confidence interval shading
    plt.plot(lengths, bbms_times, label='BBMS', marker='o', linewidth=2)
    plt.fill_between(lengths, 
                      [t - ci for t, ci in zip(bbms_times, bbms_ci)],
                      [t + ci for t, ci in zip(bbms_times, bbms_ci)],
                      alpha=0.2, label='95% CI')
    
    # Plot BBMS Basic with confidence interval shading
    plt.plot(lengths, bbms_basic_times, label='BBMS Basic', marker='o', linewidth=2)
    plt.fill_between(lengths,
                      [t - ci for t, ci in zip(bbms_basic_times, bbms_basic_ci)],
                      [t + ci for t, ci in zip(bbms_basic_times, bbms_basic_ci)],
                      alpha=0.2, label='95% CI')
    
    # Plot DijkstraPrims with confidence interval shading
    plt.plot(lengths, dijkstraprims_times, label='DijkstraPrims', marker='o', linewidth=2)
    plt.fill_between(lengths,
                      [t - ci for t, ci in zip(dijkstraprims_times, dijkstraprims_ci)],
                      [t + ci for t, ci in zip(dijkstraprims_times, dijkstraprims_ci)],
                      alpha=0.2, label='95% CI')
    
    

    plt.xlabel('Polyline Length')
    plt.ylabel('Mean Runtime (seconds)')
    plt.title('Polyline Length vs Runtime')
    plt.tight_layout()
    plt.legend()
    plt.grid()
    plt.savefig('polyline_length_effect.png', dpi=300)
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
            'bbms_basic': [],
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
            bbms_basic_time = run_benchmark(polylines[0], polylines[1], 'bbms_basic')
            dijkstraprims_time = run_benchmark(polylines[0], polylines[1], 'dijkstraprims')

            if bbms_time is None or bbms_basic_time is None or dijkstraprims_time is None:
                print("Aborting entire experiment, because one or more algorithms failed.")
                exit(1)

            accumulated_times[length]['bbms'].append(bbms_time)
            accumulated_times[length]['bbms_basic'].append(bbms_basic_time)
            accumulated_times[length]['dijkstraprims'].append(dijkstraprims_time)

        results = {}
        for length in lengths:
            results[length] = {
                'bbms': summarize_times(accumulated_times[length]['bbms']),
                'bbms_basic': summarize_times(accumulated_times[length]['bbms_basic']),
                'dijkstraprims': summarize_times(accumulated_times[length]['dijkstraprims'])
            }

        print(f"Iteration {iteration}/{max_num_polylines} completed")
        print("Benchmark results (as table):")
        print("| Length | BBMS (mean ± CI) | BBMS Basic (mean ± CI) | DijkstraPrims (mean ± CI) |")
        print("|--------|------------------|------------------------|---------------------------|")
        for length, times in results.items():
            bbms_mean, bbms_ci = times['bbms']
            bbms_basic_mean, bbms_basic_ci = times['bbms_basic']
            dijkstraprims_mean, dijkstraprims_ci = times['dijkstraprims']
            print(f"| {length} | {bbms_mean:.4f} ± {bbms_ci:.4f} | {bbms_basic_mean:.4f} ± {bbms_basic_ci:.4f} | {dijkstraprims_mean:.4f} ± {dijkstraprims_ci:.4f} |")

        plotResults(results)
        print()


if __name__ == "__main__":
    main()