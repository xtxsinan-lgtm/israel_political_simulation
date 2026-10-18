shader_type canvas_item;

uniform float grain : hint_range(0.0, 0.4) = 0.06;
uniform vec4 ink : source_color = vec4(0.1176, 0.1098, 0.1020, 1.0);

void fragment() {
	vec4 paper = texture(TEXTURE, UV);
	float n = fract(sin(dot(UV * 240.0, vec2(12.9898, 78.233))) * 43758.5453);
	float vignette = smoothstep(0.85, 0.25, length(UV - vec2(0.5)));
	COLOR = paper;
	COLOR.rgb = mix(COLOR.rgb, ink.rgb, (n - 0.5) * grain);
	COLOR.rgb *= mix(0.86, 1.0, vignette);
}
