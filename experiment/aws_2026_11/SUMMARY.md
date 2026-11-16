# November 2026: what changed, and what the AWS run shows

This page is a quick catch-up on two days of work, 13 and 14 November 2026. The work had three parts. The first was an audit of the code, which included Wouter's three suggestions. The second was a leaner memory layout for the two BBMS variants with dead path pruning. The third was a set of fixes and additions to the datasets. A half-day run on AWS then measured all of it on one machine. On 16 November a separate AI model, given the code and data but not my conclusions, checked whether the comparison is fair. Section 6 gives its findings, and this page is corrected for them.

The July AWS run had suggested that the simpler algorithm, DijkstraPrims, beats BBMS in practice, even on inputs built to be hard. This run shows BBMS clearly ahead only on inputs where DijkstraPrims has to visit every cell. The comparison is also not fair yet, because DijkstraPrims has not had the same optimization as BBMS.

## The short version

- The audit made the two dead path pruning variants 1.2 to 9.7 times faster than the code from before the audit. The largest gain is on alternating. The running time of DijkstraPrims barely changed.
- The lean variants store the same data more compactly. They make the exact same parent choices and return the same matchings and operation counts. They use a fifth to a third of the memory, and they are 1.3 to 3.8 times faster than the versions after the audit.
- Together, the two changes took the Stepwise pruning variant on alternating at N = 11000 from 269 s before the audit to 7.9 s for BBMSDppStepwiseLean. That is 34 times faster.
- With both changes, BBMSDppStepwiseLean is faster than DijkstraPrims on every pair of the three alternating sets (4.6 to 9.7 times) and the two outlier sets (3.0 to 3.3 times). On all of these, DijkstraPrims visits every cell. On alternating at N = 30000 BBMSDppStepwiseLean takes 59 s against 461 s.
- On random the result depends on the pair. DijkstraPrims is faster on 5 of the 13 random pairs. On the pairs where it wins and the cells were counted, it visits 9 to 19 % of the cells. Where it loses, it visits 36 to 88 %. On identical it is faster on all pairs.
- After the audit, BBMSCore and BBMSInter depend strongly on which curve comes first. On alternating at N = 2300 they are 20 to 28 times faster when the two curves are swapped.
- On real-world data the result is mixed. BBMSDppStepwiseLean wins on drifter. On geolife DijkstraPrims is slightly faster, 50 s against 53 s in total, and faster on 55 % of the pairs. DijkstraPrims is about 6 times faster on pigeons.
- DijkstraPrims still stores its parents in a hash map. A plain array of one byte per cell gives exactly the same matching. In tests on a Mac it made DijkstraPrims 1.4 to 4 times faster and cut its memory by 3 to 23 times. These are Mac numbers on a few pairs, not an AWS run. With that change, the lead of BBMSDppStepwiseLean shrinks from about 3 to about 2 times on outlier. On alternating at N = 6500 it stays about 6 times. On the one random pair tested, the two were about equal. On random pairs where DijkstraPrims visits few cells it already wins, so random probably tips toward DijkstraPrims. On two large geolife pairs DijkstraPrims became faster. On the 300 drifter pairs the two were equal.
- The pigeon data has long runs of repeated points, which the logger records while a bird sits still. With the repeats removed, the grids are 23 times smaller in total. BBMSDppStepwiseLean then gets 72 times faster and DijkstraPrims 14 times, and the gap between them almost closes.
- Each pair ran once, and a synthetic number is the mean of only 1 to 3 pairs. That hides large differences between pairs, so small differences, such as a 1.2 times win, are not settled.

## The algorithms and terms

A cell (i, j) pairs point i of the first curve with point j of the second. Its value is the distance between those two points. This page never says "row" or "column", only i and j.

The code has five algorithms in two families. The BBMS family builds a tree over all cells, with (0, 0) as the root. Every other cell gets one parent. For a cell (i, j), the candidates are (i-1, j), the diagonal cell (i-1, j-1), and (i, j-1). To choose between two candidates, BBMS walks up the tree from both until the walks meet. The meeting cell is their nearest common ancestor (NCA), and one such comparison is an NCA query. Each move up the tree is one NCA step.

- **BBMSCore** is the plain version, with no extra structures.
- **BBMSInter** adds shortcuts. A shortcut is a stored jump from a cell to an ancestor several steps closer to the root, so a walk can skip cells.
- **BBMSDppStepwise** and **BBMSDppInstant** keep shortcuts too, and add dead path pruning. When a cell can get no more children and has none, the chain of cells leading to it can never be part of a matching. That chain is a dead path. Pruning removes the shortcuts on it and redirects the shortcuts that pointed into it, so later walks jump past it. The Stepwise variant walks the dead path one cell at a time and cleans up every cell on it. The Instant variant jumps straight to the cell where the dead path branches off. It cleans up only the dead cell it started from.
- **DijkstraPrims** comes from Har-Peled, Raichel and Robson. It takes cells off a heap in order of value, cheapest first, and stops when it reaches the end cell. So it can finish without visiting every cell, while every BBMS variant visits all of them.

The pruning variants now exist in three versions. "Before the audit" is the code the July run used. "After the audit" is BBMSDppStepwise and BBMSDppInstant with the audit fixes. "Lean" is BBMSDppStepwiseLean and BBMSDppInstantLean, which are the after-the-audit versions with a smaller memory layout.

## 1. The code audit

The audit made five changes to the code the July run used.

- **Two NCA queries per cell instead of three.** This was Wouter's point 3. The first query compares (i-1, j) with the diagonal cell. The second compares the winner with (i, j-1). BBMSCore and the two pruning variants also take Wouter's way of building a cell's shortcut, which extends the parent's shortcut by one step. In BBMSInter that did not work. Without pruning, the parent's shortcut is often out of date. Extending it more than doubled BBMSInter's NCA steps. So BBMSInter runs a third query, but only when its shortcut update needs the result.
- **Shortcut removal from the back of the lists.** This was Wouter's point 2. The pruning variants keep, for each cell, lists of the shortcuts that point to it. The shortcut to remove is almost always the last one, but the old code searched from the front.
- **Squared distances.** All algorithms now compare squared distances and take one square root at the end. DijkstraPrims also looks each neighbour up once in its hash map instead of twice.
- **Pruning at the last cell for each i was tested and left out.** This was Wouter's point 1. The pruning variants only check for a dead path at the diagonal candidate (i-1, j-1). The cell (i-1, n-1) is never in that position, so a dead path that ends there is never pruned. I added a check for that cell in the pruning variants. About one more path per value of i was pruned, and the number of NCA steps did not change at all on the four synthetic sets at N = 2300. A retest on 16 November, on 37 synthetic and real-world pairs, found the same for NCA steps. It did find that the lean variants then use less memory, because the pruned shortcuts are reused. The saving is 0 to 6 % on most sets, 8 to 14 % on geolife and 17 to 33 % on alternating_swapped. The time grows with it, by 2 to 12 % on most sets and 36 to 50 % on alternating_swapped. The change is not in the code, but it is saved as a patch.
- **A new test for local correctness.** A matching is locally correct if every piece of it, between any two matched cells, is itself a best matching of the two pieces of curve. The test checks this for the five original algorithms. It does not include the lean variants yet. They passed when the review added them. With many equal distances, BBMS and DijkstraPrims can return different matchings. Both are locally correct and give the same distance.

## 2. The lean dead path pruning variants

The pruning variants after the audit used about 210 bytes per cell on random. BBMSCore uses 24. About 60 % of the 210 bytes was bookkeeping. Every cell record held four list headers, which were mostly empty. List buffers were never given back. Shortcuts were never freed, even after their path died.

The lean variants change only how the data is stored, in three ways.

1. A cell's incoming shortcuts form a linked list that runs through the shortcuts themselves. That replaces the separate list per cell.
2. A dead shortcut goes on a free list, and the next new shortcut reuses it.
3. Shortcuts refer to each other by a 32-bit position instead of a 64-bit pointer.

BBMSDppStepwiseLean uses 49 bytes per cell on random, 72 on alternating and 56 on pigeons. A test compares each lean variant with its after-the-audit version on 1,214 inputs. It checks every parent choice, the matching, the distance and every operation counter. It found 0 differences, and it caught each of four deliberately planted bugs.

## 3. The datasets

Wouter asked for two kinds of new synthetic set, and both are added.

- **`alternating_cheap_column`.** In alternating, every second point of the second curve is a cheap point near the origin, and the others are a far-away barrier. A strip is the set of cells (i, j) for one cheap j and every i. The other values of j give barrier strips, which are expensive. On alternating, DijkstraPrims finishes one strip before it starts the next. In the new set, the cells (0, j), where every strip starts, are cheaper than any strip cell. So DijkstraPrims reaches the start of every strip early and then works on all strips at the same time.
- **`outlier_swapped` and `alternating_swapped`.** These hold the same pairs with the two curves exchanged.

The real-world generator had four problems, and all are fixed.

- It converted longitude and latitude to metres with a separate reference point per curve. That shifted the two curves of a pair apart, by more the further they are from longitude 0. Now both curves of a pair share one reference point.
- Curves could jump across the date line. One drifter curve had a single step of 21,290 km. Longitudes are now continuous along a curve.
- Random buoys from the whole world were mostly in different oceans. Drifter pairs now come from the 10 by 10 degree square with the most buoys.
- Nothing showed what the repeated points in the pigeon data do. The new control set `pigeons_dedup` holds the same pigeon pairs with every point removed that equals the point before it. This cannot change the discrete Fréchet distance. The raw `pigeons` set stays the main dataset, because repeated points are real data.

All old real-world results came from the faulty projection, so they should not be reused.

## 4. The AWS run

The run used one EC2 machine with 4 vCPUs and 124 GB of memory, the same type as in July. It ran on 14 November from 00:24 to 11:09 UTC. Jobs ran one at a time. A memory cap at 90 % of the machine made an algorithm that needs too much memory stop cleanly. Each real-world run had a limit of 300 s. Each pair ran once. A synthetic number is the mean over the 1 to 3 pairs in a dataset file. The runs at N = 18000 and 30000 had no counting runs, so how many cells DijkstraPrims visited there is not known.

Operation counts come from separate counting runs. The counters are compiled into a separate program, so they do not slow down the timing runs.

Memory is the peak memory of the process. On Linux that peak carried over from the Python script that started each run, so every run started at about 34 MB. A run that needed less than that shows 34 MB, whatever it really used. This hides the differences on most real-world pairs, which are small. On drifter, 74 to 99 % of the runs of each algorithm sit at that floor. All memory numbers in this summary are in gigabytes, so the floor does not change them. The July run measured memory the same way. The runner now reads the peak of its own program only, so the next run will show these small differences.

When an algorithm failed on a pair, the run skipped that algorithm's larger pairs of the same dataset. Some algorithms were also left out of the largest pairs on purpose, to keep the run to half a day. On pigeons, BBMSInter and BBMSDppInstantLean only ran on the 17 pairs below 100 million cells, and BBMSCore did not run at all.

The run produced 3,244 timing runs and 3,181 counting runs. Five timing runs ran out of memory, all as expected. Four of those were BBMSDppStepwise and BBMSDppInstant on random and alternating at N = 30000. The fifth was BBMSDppStepwise on the largest pigeon pair. Six runs hit the time limit. These were BBMSCore and BBMSInter on one geolife pair and BBMSCore on one pigeons_dedup pair, each in both the timing and the counting run.

All algorithms returned the same Fréchet distance on every pair where they finished, to the printed precision. That covers 58 synthetic pairs and 603 real-world pairs.

## 5. Results

### Did the audit help?

The table gives the time in seconds before and after the audit, on the same pairs and the same machine. It shows BBMSDppStepwise, not the lean variant.

| dataset, N | BBMSCore | BBMSInter | BBMSDppStepwise | DijkstraPrims |
|---|---|---|---|---|
| random 3900 | 18.0 → 15.4 | 4.85 → 4.66 | 5.76 → 4.29 | 2.63 → 2.59 |
| random 11000 | not run | not run | 52.7 → 35.7 | 37.2 → 36.5 |
| alternating 2300 | 159 → 130 | 364 → 317 | 2.22 → 1.18 | 1.63 → 1.58 |
| alternating 11000 | not run | not run | 269 → 27.8 | 56.2 → 56.2 |

The smallest gain is BBMSDppInstant on random at N = 2300, which got 1.2 times faster. The pruning variants now do 38 to 42 % fewer NCA steps on every set. BBMSCore does 29 % fewer on random and outlier, but none fewer on alternating. It still got 18 % faster on alternating. The likely cause is the squared distances, but that is not measured.

After the audit alone, BBMSDppStepwise beats DijkstraPrims on alternating. On random it still loses at N = 3900 and is about equal at N = 11000.

### Does the lean layout help?

The table gives the peak memory and the time of BBMSDppStepwise after the audit, its lean version, and DijkstraPrims.

| dataset, N | BBMSDppStepwise | BBMSDppStepwiseLean | DijkstraPrims |
|---|---|---|---|
| random 11000 | 25.2 GB, 35.9 s | 5.5 GB, 18.1 s | 3.4 GB, 22.2 s |
| random 18000 | 67.5 GB, 99.2 s | 14.6 GB, 53.0 s | 7.1 GB, 74.2 s |
| random 30000 | out of memory | 40.5 GB, 171 s | 47.4 GB, 353 s |
| alternating 11000 | 25.6 GB, 28.0 s | 8.1 GB, 7.93 s | 6.1 GB, 56.3 s |
| alternating 18000 | 68.9 GB, 76.9 s | 21.8 GB, 21.1 s | 15.2 GB, 158 s |
| alternating 30000 | out of memory | 60.4 GB, 59.1 s | 50.8 GB, 461 s |

BBMSDppStepwise needs about 70 GB at N = 18000 and cannot run N = 30000 on this machine. BBMSDppStepwiseLean runs N = 30000 with 40 to 60 GB. It is 1.9 to 3.6 times faster than BBMSDppStepwise. The lean layout helps the Instant variant by a similar amount, and BBMSDppInstantLean is 1.3 to 3.8 times faster than BBMSDppInstant.

In this table DijkstraPrims uses less memory than BBMSDppStepwiseLean in every case except random at N = 30000. Its random numbers are means of two or three pairs that differ a lot, and per pair it sometimes uses more. The 7.1 GB at N = 18000 is the mean of 0.4 GB and 14 GB, and the 74.2 s the mean of 2.6 s and 146 s. So the jump to 47.4 GB at N = 30000 mostly reflects which pairs were drawn. Both pairs there use as much memory as outlier at N = 30000, where DijkstraPrims visits every cell. The cells visited were not counted at these sizes, and the hash map may add to the jump.

### Who wins on synthetic data?

The table gives how many times longer DijkstraPrims takes than BBMSDppStepwiseLean, from the mean time over the pairs of each dataset file. On random the mean hides a wide spread. Per pair, the factor runs from 0.05 to 2.8, and DijkstraPrims is faster on 5 of the 13 random pairs. On the other sets in the table, every pair goes the same way.

| dataset | N = 2300 | N = 11000 | N = 30000 |
|---|---|---|---|
| random | 1.3 | 1.2 | 2.1 |
| outlier | 3.1 | 3.1 | 3.0 |
| outlier_swapped | 3.2 | 3.1 | not run |
| alternating | 4.6 | 7.1 | 7.8 |
| alternating_swapped | 5.1 | 6.1 | 7.4 |
| alternating_cheap_column | 5.6 | 8.0 | 9.7 |

On identical, DijkstraPrims finishes almost instantly, because the diagonal is a free path. There it wins easily.

On outlier, outlier_swapped and the three alternating sets, DijkstraPrims visits 99.96 to 100 % of the cells. These sets were built to be hard for it, and alternating_cheap_column was built to slow it down further. No set is built to be hard for the pruning variants. So the table shows worst cases for DijkstraPrims, not typical inputs.

**Why BBMSCore and BBMSInter are slow on alternating.** At N = 2300, BBMSCore takes about 106 NCA steps per cell on random and 2299 on alternating. That is about N. BBMSInter takes 17 and 1151. The pruning variants take about 4 on every set. The mechanism for BBMSCore goes in three steps.

1. Inside a strip, a cell's best parent is (i-1, j), the cell before it in the same strip. So each strip grows into one long chain of parents along i.
2. The chains of different strips only meet near the cells (0, j), close to the root.
3. For a cell (i, j) in a strip, the candidate (i-1, j) lies in its own strip, and the other two candidates lie in the barrier strip j-1. Their walks only meet near (0, j), so each walk is about i steps long.

Pruning removes the dead parts of those chains and redirects shortcuts past them, and the pruning variants then take about 4 steps per cell. That number is measured. The exact steps of how pruning gets there on alternating are not worked out yet.

**Why swapping the curves matters.** The first NCA query always compares (i-1, j) with the diagonal cell (i-1, j-1). On alternating, those two lie in different strips, so their walks are long. With the curves swapped, the cheap and barrier points alternate along i instead of j. For every second i, the cells (i-1, j) and (i-1, j-1) then lie next to each other in the same barrier strip, so their walks meet quickly. This explanation is not measured, but it fits the measured halving of the steps. BBMSCore does 2299 NCA steps per cell on alternating and 1152 on alternating_swapped. The old three-query code did the same number in both directions.

The time drops much more than the steps. BBMSCore goes from 131 s to 6.5 s, and BBMSInter from 326 s to 11.7 s. The rest of that gain probably comes from the order in which the code reads memory, which nothing measured directly. DijkstraPrims and BBMSDppStepwiseLean change by at most 15 % when swapped. On outlier, swapping made no difference.

**The cheap start of every strip slows DijkstraPrims by 13 to 25 %.** At N = 11000 it takes 63.6 s against 56.3 s. At N = 30000 it takes 575 s against 461 s. DijkstraPrims does the same operations on both sets, so the slowdown most likely comes from jumping between strips in memory. That is not measured either. BBMSDppStepwiseLean is not affected. It takes 7.94 s on the new set and 7.93 s on alternating.

### Who wins on real data?

The table gives the total seconds on the pairs where both algorithms finished. DijkstraPrims still uses its hash map here. In the review's test with the array version on a Mac, the 300 drifter pairs took 4.1 s with DijkstraPrims and 4.3 s with BBMSDppStepwiseLean. On two large geolife pairs, DijkstraPrims took about 0.45 s each, and BBMSDppStepwiseLean took 0.67 s and 0.97 s.

| dataset | pairs | BBMSDppStepwiseLean | DijkstraPrims | BBMSDppStepwiseLean faster on |
|---|---|---|---|---|
| drifter | 300 | 7.7 | 11.5 | 75 % of pairs |
| geolife | 231 | 53 | 50 | 45 % of pairs |
| pigeons | 36 | 2544 | 408 | 3 % of pairs |
| pigeons_dedup | 36 | 35 | 30 | 25 % of pairs |

The largest pigeon pair has 678 million cells. BBMSDppStepwise runs out of memory there. BBMSDppStepwiseLean finishes in 270 s with 34 GB. DijkstraPrims finishes in 37 s with 7 GB.

**Why DijkstraPrims wins on pigeons.** BBMSDppStepwiseLean visits every cell, while DijkstraPrims stops at the end cell. On the median pigeon pair, DijkstraPrims visits 24 % of the cells. BBMSDppStepwiseLean also spends about 3 times longer per cell on raw pigeons than on pigeons_dedup, 334 ns against 107 ns. Its NCA steps per cell are about the same on both, 4.7 and 4.2. So the extra time per cell is not explained yet.

**What removing the repeated points does.** The grids of the 36 pairs get 23 times smaller in total, from 7.6 billion cells to 0.33 billion. BBMSDppStepwiseLean gets 72 times faster, which is 23 times fewer cells and 3 times less time per cell. DijkstraPrims gets 14 times faster.

**Why repeated points hurt BBMSInter.** On the 17 raw pigeon pairs where BBMSInter ran, it took a median of 47 NCA steps per cell. On the 36 pairs without repeats it took 17. The mechanism goes in four steps.

1. A run of identical points in the first curve gives a block of consecutive i values. Inside the block, the cells (i, j) for one j all have the same value.
2. Inside the block, many comparisons tie, and the tie rule keeps choosing the same direction.
3. So each j inside the block gets its own chain of parents along i.
4. Neighbouring cells then hang on separate chains, whose common ancestor lies before the block. The walks grow with the length of the run.

BBMSCore and BBMSInter are much slower than DijkstraPrims on all real data. After its one time-out on geolife, BBMSCore skipped the 3 larger pairs, so it finished 227 of the 231. On those 227 pairs it took 2139 s in total, and DijkstraPrims took 33 s.

## 6. Is the comparison fair?

On 16 November a separate AI model judged the comparison from the code and the data, without my conclusions. Its verdict is "partly fair". Both sides ran on the same machine with the same compiler settings and the same timer. The operation counters were compiled out of both. The issues are below, most important first. The first four favour BBMS. The last two make every result less certain.

1. **DijkstraPrims has not been optimized to the same level.** BBMS got the audit and the lean layout, up to 34 times faster in total. DijkstraPrims still keeps every visited cell in a hash map, at about 55 bytes per visited cell. BBMS already keeps all cells in an array, so an array of one byte per cell is the fair choice for DijkstraPrims too. It gives the same matching. On a Mac it made DijkstraPrims 1.4 to 4 times faster and cut its memory by 3 to 23 times.
2. **Skipping the heap is not allowed.** A cell whose value is at most the current maximum could skip the heap. That gives the same distance, but the matching then fails the local correctness test in 1,692 of 2,000 trials. A locally correct matching is required, so this speed-up is out.
3. **Averages hide large differences between pairs.** On random, DijkstraPrims visits 9 % of the cells on one pair and 88 % on another. With two or three pairs per size, the winner depends on which pairs happened to be drawn. The paper needs at least 10 random pairs per size, reported per pair or as median and spread.
4. **The synthetic sets are worst cases for DijkstraPrims.** Five of the seven make it visit every cell, and none is hard for the pruning variants. They should be presented as worst cases. A new dataset is needed where one setting makes the input easier or harder for both algorithms. The real-world data should be the main result.
5. **Memory is not measured for small runs.** The 34 MB floor in section 4 hides most real-world memory. That needs a rerun with the fixed runner.
6. **Each pair ran once.**

The alternating numbers survive these checks. BBMSDppStepwiseLean stays about 6 times faster at N = 6500, even against the array version of DijkstraPrims. Alternating is still a worst case for DijkstraPrims.

## 7. Open questions to discuss

1. Should the lean variants replace the after-the-audit ones for the paper? They compute the same thing with less memory, faster.
2. Should BBMSDppInstant stay? BBMSDppInstantLean is about 5 % faster than BBMSDppStepwiseLean on the alternating sets. It is 7 to 39 % slower on random, outlier and identical. On pigeons it is about 2 times slower. On the 17 pigeon pairs where both ran, it took 374 s and BBMSDppStepwiseLean took 178 s.
3. BBMSCore and BBMSInter depend on which curve comes first, because the first NCA query always compares the same two candidates. Should the code choose the first query in a way that does not depend on which curve comes first? Or should every input run in both directions, with both reported?
4. Which new datasets should go into the paper? A review of the datasets during the audit proposed a curve and a noisy copy of it, with the noise level as a dial from easy to hard. In a small Python test of that idea, DijkstraPrims went from 0.3 % to 90 % of the cells as the noise grew, while BBMSCore's steps per cell stayed flat.
5. What is the paper's angle now? The July run suggested that the simpler algorithm wins in practice. Now the pruning variant wins clearly on inputs where DijkstraPrims must visit every cell. On random and on real data the result is mixed, and DijkstraPrims is not optimized yet. BBMSCore and BBMSInter also depend on which curve comes first.
6. Should the geolife pairs whose curves are far apart be dropped? The generator picks 22 random trips from the whole dataset and pairs every trip with every other, which gives 231 pairs. Some trips lie in other countries or continents. In 22 of the 231 pairs, the two curves lie more than 1,000 km apart, and a flat projection is rough at that distance.
7. The final numbers need several runs per pair. Where should that rerun happen, on AWS again or on the TU server?
8. Should DijkstraPrims get the array version, and maybe a faster heap, before the rerun? Section 6 argues that a fair comparison needs it.
9. Should the lean variants get the pruning at the last cell for each i (section 1)? It saves up to a third of the memory and costs up to half again as much time.

## Where to find things

- The code is on GitHub, branch `aws-run-2026-11`. It contains the audit, the lean variants, the job list `experiment/aws_2026_11/run_plan.py` and the results in `results_aws_2026_11/`.
- The command `python3 experiment/aws_2026_11/make_reports.py`, run from the repo root, writes four HTML reports to `analysis/output/aws_2026_11/`. The page `overview.html` has the headline charts. The pages `main.html`, `before_after.html` and `real_world.html` let you explore every measured attribute.
