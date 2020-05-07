
# .PHONY: run
# run: fibonacci.json
# 	myfpga fibonacci.json


fibonacci.json: fibonacci.v fibonacci.ys
	verilator --lint-only fibonacci.v -Wall -Wpedantic -Werror-width -Werror-selrange -Werror-implicit -Werror-pinmissing
	yosys fibonacci.ys


.PHONY: clean
clean:
	rm fibonacci.json
