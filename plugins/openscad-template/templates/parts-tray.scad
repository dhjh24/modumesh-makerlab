// Parts Tray — shallow open-top tray with sloped sides
// Parameters are generated in _params.scad (never user script source)

include <_params.scad>;

module _parts_tray() {
    w = box_width;
    d = box_depth;
    h = box_height;
    wt = wall_thickness;
    bt = bottom_thickness;
    cr = corner_radius;
    slope = 10;  // degrees

    base_w = w - 2 * (h - bt) * tan(slope);
    base_d = d - 2 * (h - bt) * tan(slope);

    // Hull of two rectangles at top and bottom for sloped walls
    hull() {
        // Bottom (inner floor)
        translate([0, 0, bt]) {
            linear_extrude(height = 0.01) {
                if (cr > 0) {
                    _rounded_rect(max(base_w - 2*wt, 5), max(base_d - 2*wt, 5), max(cr - 2, 0));
                } else {
                    square([max(base_w - 2*wt, 5), max(base_d - 2*wt, 5)], center = true);
                }
            }
        }
        // Top rim
        translate([0, 0, h]) {
            linear_extrude(height = 0.01) {
                if (cr > 0) {
                    _rounded_rect(w, d, cr);
                } else {
                    square([w, d], center = true);
                }
            }
        }
    }
}

module _rounded_rect(w, d, r) {
    if (r > 0) {
        hull() {
            for (x = [-w/2 + r, w/2 - r]) {
                for (y = [-d/2 + r, d/2 - r]) {
                    translate([x, y, 0]) circle(r);
                }
            }
        }
    } else {
        square([w, d], center = true);
    }
}

_parts_tray();
