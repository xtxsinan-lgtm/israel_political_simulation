shader_type canvas_item;

uniform float density : hint_range(40.0, 400.0) = 180.0;
uniform vec4 glow : source_color = vec4(0.45, 0.85, 0.45, 1.0);

void fragment() {
	COLOR = texture(TEXTURE, UV);
	float scan = 0.85 + 0.15 * sin(UV.y * density);
	COLOR.rgb = mix(COLOR.rgb, glow.rgb, 0.08) * scan;
}
