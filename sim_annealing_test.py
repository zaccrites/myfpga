
import csv
import random
from simanneal import Annealer


class MyAnnealer(Annealer):

    def __init__(self, state, data):
        self.data = data
        super().__init__(state)

    def update(self, *args, **kwargs):
        # Overridden to avoid printing progress to stderr.
        # super().update(*args, **kwargs)
        pass

    def move(self):
        initial_energy = self.energy()

        if random.uniform(0, 1) > 0.5:
            self.state += 1
        else:
            self.state -= 1

        self.state = max(self.state, 0)
        self.state = min(self.state, len(self.data) - 1)

        return self.energy() - initial_energy

    def energy(self):
        return -self.data[self.state]


def main():
    dates = []
    data = []
    # with open('FB.csv', 'r') as f:
    with open('GOOG.csv', 'r') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i == 0:
                continue
            dates.append(row[0])
            data.append(float(row[1]))

    # Start in the middle
    init_state = len(data) // 2

    solver = MyAnnealer(init_state, data)
    solver.set_schedule(solver.auto(minutes=0.1))
    state, e = solver.anneal()

    maximum = -e
    date = dates[state]
    print(f'Maximum was {maximum} on {date}')


if __name__ == '__main__':
    main()




# from scipy.optimize import dual_annealing
# import csv


# def main():
#     dates = []
#     data = []
#     # with open('FB.csv', 'r') as f:
#     with open('GOOG.csv', 'r') as f:
#         reader = csv.reader(f)
#         for i, row in enumerate(reader):
#             if i == 0:
#                 continue
#             dates.append(row[0])
#             data.append(float(row[1]))

#     # Finds the global minimum, so negate before running.
#     def func(x):
#         i = int(x[0])
#         return -data[int(x)]

#     low_bound = 0
#     high_bound = len(data) - 1
#     bounds = list(zip([low_bound], [high_bound]))
#     # seed = 1234

#     # result = dual_annealing(func, bounds=bounds, seed=seed)
#     result = dual_annealing(func, bounds=bounds)

#     index = int(result.x[0])
#     maximum = -result.fun
#     print(f'Maximum was {maximum} at {dates[index]}')


# if __name__ == '__main__':
#     main()
