
import os
import sys
import re
import subprocess
import itertools
import struct
import tempfile
from datetime import datetime

import sympy
from sympy.logic.boolalg import to_cnf, BooleanTrue, BooleanFalse


def get_solutions(clauses):
    tempdir = tempfile.mkdtemp()
    input_file_path = os.path.join(tempdir, 'solver_input.bin')
    output_file_path = os.path.join(tempdir, 'solver_output.bin')

    # TODO: Provide an interface to solve multiple systems in a single
    # run. Potentially all combinational logic circuit truth tables
    # can be solved at once.
    number_of_systems = 1

    variables = set()
    for clause in clauses:
        variables.update(abs(variable) for variable in clause)
    number_of_variables = len(variables)

    with open(input_file_path, 'wb') as f:
        f.write(struct.pack('=i', number_of_systems))
        f.write(struct.pack('=ii', number_of_variables, len(clauses)))
        for clause in clauses:
            f.write(struct.pack(f'=i{len(clause)}i', len(clause), *clause))

    # This performs well for functions with a limited number of solutions,
    # but for logic functions with dozens of variables and millions of
    # solutions it will perform poorly.
    cmd = [
        '/home/zac/myfpga-build/minisat_interface/minisat_interface',
        input_file_path,
        output_file_path,
    ]
    subprocess.check_call(cmd)

    with open(output_file_path, 'rb') as f:
        def read_and_unpack(fmt):
            size = struct.calcsize(fmt)
            data = f.read(size)
            return struct.unpack(fmt, data)

        number_of_systems, = read_and_unpack('=i')
        assert number_of_systems == 1

        number_of_variables, number_of_solutions = read_and_unpack('=ii')
        for _ in range(number_of_solutions):
            solution = read_and_unpack(f'={number_of_variables}i')
            yield tuple(bool(x) for x in solution)


def main():
    # For a mux:
    # Expected Truth Table
    #
    # x1 x2 x3 | y
    # ---------+---
    #  0  0  0 | 0
    #  0  0  1 | 0
    #  0  1  0 | 0
    #  0  1  1 | 1    (-1,  2,  3, 0)
    #  1  0  0 | 1    ( 1, -2, -3, 0)
    #  1  0  1 | 0
    #  1  1  0 | 1    ( 1,  2, -3, 0)
    #  1  1  1 | 1    ( 1,  2,  3, 0)
    x1, x2, x3 = sympy.symbols(['x1', 'x2', 'x3'])
    y = x1 & ~x3 | x2 & x3

    # For checking a specific 64 bit number:
    number = 0xdeadbeefcafebabe
    variables = sympy.symbols([f'x{i+1}' for i in range(64)])
    y = BooleanTrue()
    for i, variable in enumerate(variables):
        if number & (1 << i):
            y &= variable
        else:
            y &= ~variable

    # print(to_cnf(y))
    clauses = str(to_cnf(y)).split(' & ')
    clauses = [clause.lstrip('(').rstrip(')').replace(' |', '').replace('~', '-') for clause in clauses]
    clauses = [clause.replace('x', '') for clause in clauses]
    clauses = [tuple(int(part) for part in clause.split()) for clause in clauses]

    start = datetime.now()
    solutions = list(get_solutions(clauses))

    if len(solutions) == 0:
        print('No solutions!')
        return 1
    elif len(solutions) == 1:
        print('One unique solution')
    else:
        print(f'{len(solutions)} solutions')

    print(f'Found in {(datetime.now() - start).total_seconds():.3f} seconds')

    # num_variables = len(solutions[0])
    # solutions = set(solutions)

    # for possible_solution in itertools.product([False, True], repeat=num_variables):
    #     result_bit = '1' if possible_solution in solutions else '0'
    #     term_bits = ['1' if value else '0' for value in possible_solution]

    #     # if result_bit == '1':
    #     # print(f'{" ".join(term_bits)} | {result_bit}')


if __name__ == '__main__':
    sys.exit(main())
