shader_type canvas_item;

uniform float reveal : hint_range(0.0, 1.0) = 1.0;
uniform vec4 stamp : source_color = vec4(0.722, 0.161, 0.184, 0.9);

void fragment() {
	COLOR = texture(TEXTURE, UV);
	float edge = smoothstep(reveal - 0.08, reveal, length(UV - vec2(0.5)));
	COLOR.rgb = mix(stamp.rgb, COLOR.rgb, edge);
	COLOR.a *= mix(stamp.a, COLOR.a, edge);
}
