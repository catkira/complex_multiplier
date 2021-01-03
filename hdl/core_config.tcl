set display_name {Complex Multiplier}

set core [ipx::current_core]

set_property DISPLAY_NAME $display_name $core
set_property DESCRIPTION $display_name $core

core_parameter INPUT_WIDTH_A {AXI DATA WIDTH} {Width of the AXIS data-in-a bus}
core_parameter INPUT_WIDTH_B {AXI ADDR WIDTH} {Width of the AXIS data-in-b bus}
core_parameter OUTPUT_WIDTH  {AXI ADDR WIDTH} {Width of the AXIS data-out bus}
core_parameter TRUNCATE      {BIT} {Select between truncation and rounding}
core_parameter STAGES        {INT} {Number of pipeline stages (min=2)}

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