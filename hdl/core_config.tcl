set display_name {Complex Multiplier}

set core [ipx::current_core]

set_property DISPLAY_NAME $display_name $core
set_property DESCRIPTION $display_name $core

core_parameter OPERAND_WIDTH_A {OPERAND WIDTH A} {Width of the data-in-a operands}
core_parameter OPERAND_WIDTH_B {OPERAND WIDTH B} {Width of the data-in-b operands}
core_parameter OPERAND_WIDTH_OUT  {OPERAND WIDTH OUT} {Width of the data-out operands}
core_parameter TRUNCATE      {TRUNCATE} {Select between truncation and rounding}
core_parameter STAGES        {STAGES} {Number of pipeline stages (min=2)}

set bus [ipx::get_bus_interfaces -of_objects $core s_axis_a]
set_property NAME s_axis_a $bus
set_property INTERFACE_MODE slave $bus

set bus [ipx::get_bus_interfaces aclk]
set parameter [ipx::get_bus_parameters -of_objects $bus ASSOCIATED_BUSIF]
set_property VALUE s_axis_a $parameter

set bus [ipx::get_bus_interfaces -of_objects $core s_axis_b]
set_property NAME s_axis_b $bus
set_property INTERFACE_MODE slave $bus

set bus [ipx::get_bus_interfaces aclk]
set parameter [ipx::get_bus_parameters -of_objects $bus ASSOCIATED_BUSIF]
set_property VALUE s_axis_b $parameter

set bus [ipx::get_bus_interfaces -of_objects $core m_axis]
set_property NAME m_axis $bus
set_property INTERFACE_MODE master $bus

set bus [ipx::get_bus_interfaces aclk]
set parameter [ipx::get_bus_parameters -of_objects $bus ASSOCIATED_BUSIF]
set_property VALUE m_axis $parameter