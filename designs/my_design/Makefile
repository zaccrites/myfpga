
# .PHONY: run
# run: my_design.json
# 	myfpga my_design.json


my_design.json: my_design.v my_design.ys
	verilator --lint-only my_design.v -Wall -Wpedantic -Werror-width -Werror-selrange -Werror-implicit -Werror-pinmissing
	yosys my_design.ys


.PHONY: clean
clean:
	rm my_design.json
