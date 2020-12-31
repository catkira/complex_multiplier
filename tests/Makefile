PWD=$(shell pwd)
SIM=verilator
VERILATOR_TRACE=1

VERILOG_SOURCES = $(PWD)/../hdl/complex_multiplier.v

TOPLEVEL := complex_multiplier
MODULE := test_complex_multiplier

ifeq ($(SIM),verilator)
    EXTRA_ARGS += $(PWD)/verilator_waiver.vlt
endif

include $(shell cocotb-config --makefiles)/Makefile.sim