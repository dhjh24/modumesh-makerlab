// Grid Organizer — parametric compartment box
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

module _grid_organizer() {
    w = box_width;
    d = box_depth;
    h = box_height;
    wt = wall_thickness;
    bt = bottom_thickness;
    cr = corner_radius;
    cx = grid_cells_x;
    cy = grid_cells_y;

    inner_w = w - 2*wt;
    inner_d = d - 2*wt;
    cell_w = inner_w / cx;
    cell_d = inner_d / cy;

    difference() {
        // Outer shell
        linear_extrude(height = h) {
            _rounded_rect(w, d, cr);
        }
        // Inner cavity
        translate([0, 0, bt]) {
            linear_extrude(height = h - bt + 0.01) {
                _rounded_rect(inner_w, inner_d, max(cr - wt, 0));
            }
        }
    }

    // Grid dividers
    color("gray") {
        // X dividers (along width)
        for (i = [1:cx-1]) {
            x = -w/2 + wt + i * cell_w;
            translate([x, 0, bt]) {
                cube([wt, inner_d, h - bt]);
            }
        }
        // Y dividers (along depth)
        for (j = [1:cy-1]) {
            y = -d/2 + wt + j * cell_d;
            translate([0, y, bt]) {
                cube([inner_w, wt, h - bt]);
            }
        }
    }
}

_grid_organizer();
