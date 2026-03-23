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
endingLength = 5000
step = 250
num_polylines = 10  # Number of random polylines to generate for each length (must be even)


def run_benchmark(polylines, algorithm):
    pair_times = []
    current_index = 1

    while current_index <= len(polylines) - 1:
        # Run the specified algorithm and time each pair
        try:
            start = time.perf_counter()
            
            if algorithm == 'bbms':
                BBMS(polylines[current_index - 1], polylines[current_index])
            elif algorithm == 'bbms_basic':
                BBMS_basic(polylines[current_index - 1], polylines[current_index])
            elif algorithm == 'dijkstraprims':
                DijkstraPrims(polylines[current_index - 1], polylines[current_index])
            else:
                print(f"Unknown algorithm: {algorithm}")
                return None
            
            end = time.perf_counter()
            pair_times.append(end - start)
            
        except Exception as e:
            print(f"Error running {algorithm} on polylines {current_index - 1} and {current_index}: {e}")
            current_index += 2
            return None

        # Move to the next pair of polylines (in order)
        current_index += 2

    # Calculate mean time and 95% confidence interval half-width
    mean_time = np.mean(pair_times)
    std_error = stats.sem(pair_times)
    ci_half_width = std_error * stats.t.ppf(0.975, len(pair_times) - 1)
    
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


def main():
    """ Runs each algorithm on differently sized polylines to analyze the effect of polyline length on runtime. """

    # Print the parameters of the experiment
    print(f"Experiment parameters:")
    print(f"  Starting length: {startingLength}")
    print(f"  Ending length: {endingLength}")
    print(f"  Step: {step}")
    print(f"  Number of polylines per length: {num_polylines}")
    print()

    results = {}

    for length in range(startingLength, endingLength + 1, step):
        print(f"Running benchmark for polylines of length {length}...")

        polylines = generate_random_polylines(num_polylines=num_polylines, length_range=(length, length), x_range=(0, 10), y_range=(0, 10))
        
        bbms_time = run_benchmark(polylines, 'bbms')
        bbms_basic_time = run_benchmark(polylines, 'bbms_basic')
        dijkstraprims_time = run_benchmark(polylines, 'dijkstraprims')

        if bbms_time is None or bbms_basic_time is None or dijkstraprims_time is None:
            print(f"Aborting entire experiment, because one or more algorithms failed.")
            exit(1)

        results[length] = {
            'bbms': bbms_time,
            'bbms_basic': bbms_basic_time,
            'dijkstraprims': dijkstraprims_time
        }

        print()


    print("Benchmark results (as table):")
    print("| Length | BBMS (mean ± CI) | BBMS Basic (mean ± CI) | DijkstraPrims (mean ± CI) |")
    print("|--------|------------------|------------------------|---------------------------|")
    for length, times in results.items():
        bbms_mean, bbms_ci = times['bbms']
        bbms_basic_mean, bbms_basic_ci = times['bbms_basic']
        dijkstraprims_mean, dijkstraprims_ci = times['dijkstraprims']
        print(f"| {length} | {bbms_mean:.4f} ± {bbms_ci:.4f} | {bbms_basic_mean:.4f} ± {bbms_basic_ci:.4f} | {dijkstraprims_mean:.4f} ± {dijkstraprims_ci:.4f} |")


    plotResults(results)

if __name__ == "__main__":
    main()