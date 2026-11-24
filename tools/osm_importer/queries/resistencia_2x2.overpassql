// Four blocks (2 x 2) bounded by Remedios de Escalada, Bartolome Mitre,
// Marcelo Torcuato de Alvear and Corrientes, Resistencia, Chaco.
// Bbox = corner intersections (computed from OSM street geometry,
// 2026-11-24) plus ~70 m margin. Order: south, west, north, east.
// Every node and way in the bbox plus multipolygon/building relations.
// Route relations (bus lines) are excluded: they span the whole city.
[out:json][timeout:120][bbox:-27.4503,-58.9890,-27.4458,-58.9840];
(
  node;
  way;
  relation["type"~"^(multipolygon|building)$"];
);
(._;>;);
out meta;
