
import subprocess

clauses = [
    (1, 0),
    (2, 0),
    (3, 0),
    (4, 0),
    (5, 0),
    (6, 0),
    (7, 0),
    (8, 0),
    (-9, 0),
    (-10, 0),
    (-11, 0),
    (-12, 0),
    (-13, 0),
    (-14, 0),
    (-15, 0),
    (-16, 0),
    (17, 0),
    (18, 0),
    (19, 0),
    (20, 0),
    (21, 0),
    (22, 0),
    (23, 0),
    (24, 0),
    (-25, 0),
    (-26, 0),
    (-27, 0),
    (-28, 0),
    (-29, 0),
    (-30, 0),
    (-31, 0),
    (-32, 32, 0),
]

def get_solutions():
    solutions = []
    while True:
        script_lines = []
        for clause in clauses:
            script_lines.append(' '.join(str(term) for term in clause))
        script = '\n'.join(script_lines).encode('utf-8')

        with open('minisat2.txt', 'w') as f:
            f.write('\n'.join(script_lines))

        # TODO: Write to temporary files, or figure out how to use stdin/stdout.
        # Writing to a StringIO file would be ideal.
        cmd = ['minisat', 'minisat2.txt', 'minisat2_output.txt']
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.communicate()

        assert p.returncode in {10, 20}
        is_satisfiable = p.returncode == 10

        if not is_satisfiable:
            return solutions

        with open('minisat2_output.txt') as f:
            contents = f.read()
            solution = tuple(int(term) for term in contents.splitlines()[1].split())

        assert solution not in solutions
        solutions.append(solution)
        clauses.append(tuple(-term for term in solution))


solutions = get_solutions()
for solution in solutions:
    print(solution)
