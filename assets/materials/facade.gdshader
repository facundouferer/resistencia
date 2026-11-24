// Procedural facade (procedural_facade_v2): stylized, not real appearance.
// Walls: tileable plaster or brick (CC0, Poly Haven) tinted with the
// building's facade colour, one window per bay and level, shopfront or
// garage on the ground floor, balconies, brick plinth and a darker cornice.
// Roofs: clay tiles on pitched roofs, concrete on flat roofs.
// Everything is mapped in world space, so the generated meshes need no UVs.
shader_type spatial;

instance uniform vec3 facade_color : source_color = vec3(0.85, 0.8, 0.7);
instance uniform float base_y = 0.15;
instance uniform float top_y = 6.15;
// 0 = shopfront, 1 = residential windows, 2 = garage door.
instance uniform float ground_floor_kind = 0.0;
instance uniform vec4 roof_tint : source_color = vec4(0.42, 0.41, 0.4, 1.0);
// rgb = colour of a base band (e.g. brick plinth); a = 1 to draw it.
instance uniform vec4 base_band = vec4(0.0);
instance uniform float balconies = 0.0;
instance uniform float bay = 3.2;
// 0 = plaster, 1 = brick.
instance uniform float wall_material = 0.0;

uniform vec3 glass_color : source_color = vec3(0.1, 0.14, 0.18);
uniform vec3 frame_color : source_color = vec3(0.93, 0.92, 0.88);
uniform vec3 door_color : source_color = vec3(0.55, 0.55, 0.57);
uniform float level_height = 3.0;
uniform vec3 balcony_color : source_color = vec3(0.2, 0.2, 0.22);
uniform float base_band_height = 1.0;
uniform float cornice_band = 0.6;
uniform float normal_strength = 1.0;

// Tileable materials. *_size = real-world metres covered by one tile;
// *_mean = mean linear albedo, used to tint while keeping the texture detail.
uniform sampler2D plaster_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D plaster_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D plaster_rough : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform vec3 plaster_mean = vec3(0.405, 0.364, 0.349);
uniform float plaster_size = 2.0;
uniform sampler2D brick_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D brick_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D brick_rough : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform vec3 brick_mean = vec3(0.1392, 0.0766, 0.051);
uniform float brick_size = 3.0;
uniform sampler2D tiles_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D tiles_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D tiles_rough : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform vec3 tiles_mean = vec3(0.113, 0.0369, 0.0131);
uniform float tiles_size = 4.0;
uniform sampler2D concrete_albedo : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D concrete_normal : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D concrete_rough : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform vec3 concrete_mean = vec3(0.1456, 0.1248, 0.0976);
uniform float concrete_size = 2.5;

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

// Texture colour scaled so its mean equals `tint`.
vec3 tinted(vec3 texel, vec3 mean, vec3 tint) {
	return texel / max(mean, vec3(0.001)) * tint;
}

// Tangent-space normal map sample -> world-space normal.
vec3 world_normal_from_map(vec3 map, vec3 t, vec3 b, vec3 n) {
	vec3 m = map * 2.0 - 1.0;
	m.xy *= normal_strength;
	return normalize(t * m.x + b * m.y + n * m.z);
}

void fragment() {
	// Face normal from screen-space derivatives: exact per triangle, independent of
	// the (averaged) vertex normals, which tilted roof edges into the wall branch.
	vec3 n = normalize(cross(dFdx(world_pos), dFdy(world_pos)));
	if (dot(n, CAMERA_POSITION_WORLD - world_pos) < 0.0) {
		n = -n;
	}
	vec3 shading_normal = n;
	if (n.y > 0.5) {
		vec2 downhill = n.xz;
		if (length(downhill) > 0.1) {
			// Pitched roof: tile rows parallel to the ridge.
			vec2 d = normalize(downhill);
			vec3 along = vec3(-d.y, 0.0, d.x);
			vec3 up_slope = normalize(cross(n, along));
			vec2 uv = vec2(dot(world_pos, along), -dot(world_pos, up_slope)) / tiles_size;
			ALBEDO = tinted(texture(tiles_albedo, uv).rgb, tiles_mean, roof_tint.rgb);
			ROUGHNESS = texture(tiles_rough, uv).r;
			shading_normal = world_normal_from_map(texture(tiles_normal, uv).rgb, along, up_slope, n);
		} else {
			vec2 uv = world_pos.xz / concrete_size;
			ALBEDO = tinted(texture(concrete_albedo, uv).rgb, concrete_mean, roof_tint.rgb);
			ROUGHNESS = texture(concrete_rough, uv).r;
			shading_normal = world_normal_from_map(texture(concrete_normal, uv).rgb, vec3(1, 0, 0), vec3(0, 0, -1), n);
		}
	} else {
		vec3 tangent = normalize(vec3(-n.z, 0.0, n.x));
		vec3 up = vec3(0.0, 1.0, 0.0);
		float u = dot(world_pos, tangent);
		float h = world_pos.y - base_y;

		bool brick = wall_material > 0.5;
		vec2 wall_uv = vec2(u, -world_pos.y) / (brick ? brick_size : plaster_size);
		vec3 wall_color = brick
			? tinted(texture(brick_albedo, wall_uv).rgb, brick_mean, facade_color)
			: tinted(texture(plaster_albedo, wall_uv).rgb, plaster_mean, facade_color);
		float wall_rough = brick ? texture(brick_rough, wall_uv).r : texture(plaster_rough, wall_uv).r;
		vec3 wall_map = brick ? texture(brick_normal, wall_uv).rgb : texture(plaster_normal, wall_uv).rgb;

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
		float plinth = base_band.a * step(h, base_band_height) * (1.0 - glass * has_openings) * (1.0 - door * has_openings);

		vec3 color = wall_color;
		if (plinth > 0.5) {
			vec2 plinth_uv = vec2(u, -world_pos.y) / brick_size;
			color = tinted(texture(brick_albedo, plinth_uv).rgb, brick_mean, base_band.rgb);
			wall_rough = texture(brick_rough, plinth_uv).r;
			wall_map = texture(brick_normal, plinth_uv).rgb;
		}
		color = mix(color, frame_color, frame * has_openings);
		color = mix(color, glass_color, glass * has_openings);
		color = mix(color, door_color, door * has_openings);
		// Balcony slab and railing under upper-floor windows.
		float rail = (ground_floor ? 0.0 : balconies)
			* inside(cell, vec2(0.18, 0.06), vec2(0.82, 0.26)) * has_openings;
		color = mix(color, balcony_color, rail * (step(0.22, cell.y) + step(fract(cell.x * 12.0), 0.25) * 0.8));
		color = mix(color, color * 0.78, cornice);

		float flat_part = clamp((frame + door + rail) * has_openings, 0.0, 1.0);
		ALBEDO = color;
		ROUGHNESS = mix(mix(wall_rough, 0.6, flat_part), 0.15, glass * has_openings);
		shading_normal = normalize(mix(world_normal_from_map(wall_map, tangent, up, n), n, flat_part));
	}
	NORMAL = normalize((VIEW_MATRIX * vec4(shading_normal, 0.0)).xyz);
}
