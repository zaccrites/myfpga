

.PHONY: run


run: my_design.json
	python myfpga_toolchain.py my_design.json


my_design.json: my_design.v my_design.ys
	verilator --lint-only my_design.v
	yosys my_design.ys
