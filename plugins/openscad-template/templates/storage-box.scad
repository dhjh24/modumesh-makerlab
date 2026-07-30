// Storage Box — parametric OpenSCAD template
// Parameters are generated in _params.scad (never user script source)

include <_params.scad>;

module _fillet_2d(r) {
    if (r > 0) offset(r) offset(-r) offset(r) children();
    else children();
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

module _storage_box_body() {
    w = box_width;
    d = box_depth;
    h = box_height;
    wt = wall_thickness;
    bt = bottom_thickness;
    cr = corner_radius;

    difference() {
        // Outer shell
        linear_extrude(height = h) {
            _rounded_rect(w, d, cr);
        }
        // Inner cavity
        translate([0, 0, bt]) {
            linear_extrude(height = h - bt + 0.01) {
                _rounded_rect(w - 2*wt, d - 2*wt, max(cr - wt, 0));
            }
        }
    }
}

module _lid() {
    w = box_width + lid_clearance * 2;
    d = box_depth + lid_clearance * 2;
    h = 6;  // lid height
    wt = wall_thickness;
    cr = corner_radius;
    lc = lid_clearance;

    // Lid top
    difference() {
        linear_extrude(height = h) {
            _rounded_rect(w + wt, d + wt, cr + 1);
        }
        // Inner recess
        translate([0, 0, 2]) {
            linear_extrude(height = h - 1.5) {
                _rounded_rect(w - wt, d - wt, max(cr - 0.5, 0));
            }
        }
    }

    // Lid lip (inserts into box)
    translate([0, 0, h]) {
        linear_extrude(height = 4) {
            _rounded_rect(w - lc - 0.2, d - lc - 0.2, max(cr - 0.5, 0));
        }
    }
}

module _storage_box() {
    union() {
        _storage_box_body();
        if (include_lid) {
            translate([0, 0, box_height + 2]) _lid();
        }
    }
}

_storage_box();
