class_name GeoReference
extends RefCounted
## Converts between projected coordinates (EPSG:32721, metres) and Godot
## world positions. The only place that knows the scenario origin.
##
## godot.x = easting - origin_easting
## godot.y = height
## godot.z = -(northing - origin_northing)
##
## Projected values are passed as separate 64-bit floats: Vector3 is 32-bit
## and would lose centimetres at UTM magnitudes (~7,000,000 m).

var projection := ""
var origin_easting := 0.0
var origin_northing := 0.0


static func from_metadata(metadata: Dictionary) -> GeoReference:
	var geo := GeoReference.new()
	geo.projection = metadata["projection"]
	geo.origin_easting = float(metadata["origin"]["easting"])
	geo.origin_northing = float(metadata["origin"]["northing"])
	return geo


func projected_to_godot(easting: float, northing: float, height := 0.0) -> Vector3:
	return Vector3(easting - origin_easting, height, -(northing - origin_northing))


## Returns {"easting": float, "northing": float, "height": float}.
func godot_to_projected(position: Vector3) -> Dictionary:
	return {
		"easting": origin_easting + position.x,
		"northing": origin_northing - position.z,
		"height": position.y,
	}


## Local plane coordinates as written in scenario.json ([x, y] = [E - E0, N - N0]).
static func local_to_godot(local: Array, height := 0.0) -> Vector3:
	return Vector3(local[0], height, -local[1])
