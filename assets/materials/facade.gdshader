// Procedural facade (procedural_facade_v1): stylized, not real appearance.
// Walls: one window per bay and level, shopfront on the ground floor and a
// darker band at the cornice. Roofs: flat roof colour. Works in world space,
// so the generated meshes need no UVs.
shader_type spatial;

instance uniform vec3 facade_color : source_color = vec3(0.85, 0.8, 0.7);
instance uniform float base_y = 0.15;
instance uniform float top_y = 6.15;
// 0 = shopfront, 1 = residential windows, 2 = garage door.
instance uniform float ground_floor_kind = 0.0;
instance uniform vec3 roof_tint : source_color = vec3(0.42, 0.41, 0.4);
// rgb = colour of a base band (e.g. brick plinth); a = 1 to draw it.
instance uniform vec4 base_band = vec4(0.0);
instance uniform float balconies = 0.0;
instance uniform float bay = 3.2;

uniform vec3 glass_color : source_color = vec3(0.1, 0.14, 0.18);
uniform vec3 frame_color : source_color = vec3(0.93, 0.92, 0.88);
uniform vec3 door_color : source_color = vec3(0.55, 0.55, 0.57);
uniform float level_height = 3.0;
uniform vec3 balcony_color : source_color = vec3(0.2, 0.2, 0.22);
uniform float base_band_height = 1.0;
uniform float cornice_band = 0.6;

varying vec3 world_pos;
varying vec3 world_normal;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

float inside(vec2 p, vec2 lo, vec2 hi) {
	vec2 s = step(lo, p) * step(p, hi);
	return s.x * s.y;
}

void fragment() {
	if (world_normal.y > 0.5) {
		ALBEDO = roof_tint;
		ROUGHNESS = 0.95;
	} else {
		vec3 tangent = normalize(vec3(-world_normal.z, 0.0, world_normal.x));
		float u = dot(world_pos, tangent);
		float h = world_pos.y - base_y;
		vec2 cell = vec2(fract(u / bay), fract(h / level_height));
		bool ground_floor = h < level_height;
		bool shopfront = ground_floor && ground_floor_kind < 0.5;
		bool garage = ground_floor && ground_floor_kind > 1.5;
		float cornice = step(top_y - cornice_band, world_pos.y);
		float glass = shopfront
			? inside(cell, vec2(0.08, 0.04), vec2(0.92, 0.78))
			: (garage ? 0.0 : inside(cell, vec2(0.30, 0.28), vec2(0.70, 0.80)));
		float frame = shopfront
			? inside(cell, vec2(0.06, 0.02), vec2(0.94, 0.82))
			: (garage ? inside(cell, vec2(0.10, 0.0), vec2(0.90, 0.75))
				: inside(cell, vec2(0.27, 0.24), vec2(0.73, 0.84)));
		float door = garage ? inside(cell, vec2(0.12, 0.0), vec2(0.88, 0.72)) : 0.0;
		// No windows in the cornice band nor in a partial top level.
		float has_openings = (1.0 - cornice) * step(h + level_height * 0.3, top_y - base_y);
		vec3 color = facade_color;
		color = mix(color, frame_color, frame * has_openings);
		color = mix(color, glass_color, glass * has_openings);
		color = mix(color, door_color, door * has_openings);
		// Balcony slab and railing under upper-floor windows.
		float rail = (ground_floor ? 0.0 : balconies)
			* inside(cell, vec2(0.18, 0.06), vec2(0.82, 0.26)) * has_openings;
		color = mix(color, balcony_color, rail * (step(0.22, cell.y) + step(fract(cell.x * 12.0), 0.25) * 0.8));
		color = mix(color, base_band.rgb, base_band.a * step(h, base_band_height) * (1.0 - glass) * (1.0 - door));
		color = mix(color, facade_color * 0.78, cornice);
		ALBEDO = color;
		ROUGHNESS = mix(0.9, 0.15, glass * has_openings);
	}
}
