PWD     =  $(shell pwd)
SIM     =  verilator
VERILATOR_TRACE = 1

DUT         = complex_multiplier
TOPLEVEL    = $(DUT)
MODULE      = test_$(DUT)

VERILOG_SOURCES = $(PWD)/../hdl/$(DUT).v

# module parameters
export INPUT_WIDTH_A ?= 24
export INPUT_WIDTH_B ?= 16
export OUTPUT_WIDTH   ?= 24
export BLOCKING       ?= 1
export TRUNCATE       ?= 1
export STAGES	      ?= 3


ifeq ($(SIM), verilator)
    EXTRA_ARGS += $(PWD)/verilator_waiver.vlt
	#COMPILE_ARGS += -Wno-SELRANGE -Wno-WIDTH -Wno-CASEINCOMPLETE

	COMPILE_ARGS += -GINPUT_WIDTH_A=$(INPUT_WIDTH_A)
	COMPILE_ARGS += -GINPUT_WIDTH_B=$(INPUT_WIDTH_B)
	COMPILE_ARGS += -GOUTPUT_WIDTH=$(OUTPUT_WIDTH)
	COMPILE_ARGS += -GBLOCKING=$(BLOCKING)
	COMPILE_ARGS += -GTRUNCATE=$(TRUNCATE)
	COMPILE_ARGS += -GSTAGES=$(STAGES)
endif


include $(shell cocotb-config --makefiles)/Makefile.sim