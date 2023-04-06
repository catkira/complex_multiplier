set display_name {Complex Multiplier}

set core [ipx::current_core]

set_property DISPLAY_NAME $display_name $core
set_property DESCRIPTION $display_name $core

core_parameter OPERAND_WIDTH_A {OPERAND WIDTH A} {Width of the data-in-a operands}
core_parameter OPERAND_WIDTH_B {OPERAND WIDTH B} {Width of the data-in-b operands}
core_parameter OPERAND_WIDTH_OUT  {OPERAND WIDTH OUT} {Width of the data-out operands}
core_parameter ROUND_MODE      {ROUND MODE} {Does truncation if 0, random rounding with rounding_cy if 1}
core_parameter STAGES        {STAGES} {Number of pipeline stages (min=2)}
core_parameter BYTE_ALIGNED        {BYTE_ALIGNED} {select whether port sizes have to be multiples of 8}

set bus [ipx::get_bus_interfaces -of_objects $core s_axis_a]
set_property NAME S_AXIS_A $bus
set_property INTERFACE_MODE slave $bus

set bus [ipx::get_bus_interfaces -of_objects $core s_axis_b]
set_property NAME S_AXIS_B $bus
set_property INTERFACE_MODE slave $bus

set bus [ipx::get_bus_interfaces -of_objects $core m_axis_dout]
set_property NAME M_AXIS_DOUT $bus
set_property INTERFACE_MODE master $bus

set bus [ipx::get_bus_interfaces aclk]
set parameter [ipx::get_bus_parameters -of_objects $bus ASSOCIATED_BUSIF]
set_property VALUE S_AXIS_A:S_AXIS_B:M_AXIS_DOUT $parameter

# set tie off to prevent vivado GUI warning
set_property driver_value 0 [ipx::get_ports rounding_cy -of_objects [ipx::current_core]]