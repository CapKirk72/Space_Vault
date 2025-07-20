import math
import pygame # For pygame.math.Vector2 if needed for more complex SAT

# Placeholder for actual collision functions. 
# These will need to be implemented properly with SAT for squares.

# --- Vector Math Helpers ---
def subtract_vectors(v1, v2):
    return (v1[0] - v2[0], v1[1] - v2[1])

def dot_product(v1, v2):
    return v1[0] * v2[0] + v1[1] * v2[1]

def magnitude_sq(v):
    return v[0]**2 + v[1]**2

def normalize_vector(v):
    mag_sq = magnitude_sq(v)
    if mag_sq == 0:
        return (0,0) # Or raise an error, depending on desired behavior
    mag = math.sqrt(mag_sq)
    return (v[0] / mag, v[1] / mag)

# --- SAT Helper ---
def get_axes(vertices):
    """ Get all unique axes (normals) of a polygon's edges. """
    axes = []
    for i in range(len(vertices)):
        p1 = vertices[i]
        p2 = vertices[(i + 1) % len(vertices)] # Next vertex, wrap around
        
        edge = subtract_vectors(p2, p1)
        # Perpendicular vector (normal)
        normal = (-edge[1], edge[0]) 
        # It's good practice to normalize, though SAT works with non-normalized axes too.
        # For simplicity here, we might skip normalization in projection if consistent.
        # However, for finding minimum translation vector (MTV), normalization is key.
        # Let's normalize for robustness.
        normalized_normal = normalize_vector(normal)
        
        # Avoid adding duplicate axes (e.g. (0,1) and (0,-1) represent the same axis line)
        # A more robust check would compare normalized axes and their negatives.
        # For convex polygons like squares, just checking one direction is usually fine.
        is_duplicate = False
        for ax in axes:
            # Check if normalized_normal or its negative is already present
            if abs(dot_product(ax, normalized_normal) - 1.0) < 1e-6 or \
               abs(dot_product(ax, normalized_normal) + 1.0) < 1e-6:
                is_duplicate = True
                break
        if not is_duplicate and (normalized_normal[0] != 0 or normalized_normal[1] != 0):
             axes.append(normalized_normal)
    return axes

def project_polygon(axis, vertices):
    """ Project all vertices of a polygon onto an axis and return the min/max projection. """
    min_proj = dot_product(vertices[0], axis)
    max_proj = min_proj
    for i in range(1, len(vertices)):
        projection = dot_product(vertices[i], axis)
        if projection < min_proj:
            min_proj = projection
        elif projection > max_proj:
            max_proj = projection
    return min_proj, max_proj

# --- Collision Functions ---
def check_circle_circle_collision(c1_pos_x, c1_pos_y, c1_radius, c2_pos_x, c2_pos_y, c2_radius) -> bool:
    distance_sq = (c1_pos_x - c2_pos_x)**2 + (c1_pos_y - c2_pos_y)**2
    radii_sum_sq = (c1_radius + c2_radius)**2
    return distance_sq <= radii_sum_sq

def check_square_square_collision(sq1_world_verts: list[tuple[float, float]], sq2_world_verts: list[tuple[float, float]]) -> bool:
    """ 
    Separating Axis Theorem (SAT) based collision for two convex polygons (squares).
    sq1_world_verts and sq2_world_verts should be lists of (x, y) tuples representing vertices in order.
    """
    axes1 = get_axes(sq1_world_verts)
    axes2 = get_axes(sq2_world_verts)

    for axis in axes1 + axes2: # Check all unique axes from both polygons
        min1, max1 = project_polygon(axis, sq1_world_verts)
        min2, max2 = project_polygon(axis, sq2_world_verts)
        
        # Check for separation on this axis
        if max1 < min2 or max2 < min1:
            return False # Found a separating axis, no collision
            
    return True # No separating axis found, polygons are colliding

def get_closest_point_on_segment(p, a, b):
    """Finds the closest point on line segment AB to point P."""
    ap = subtract_vectors(p, a)
    ab = subtract_vectors(b, a)
    ab_mag_sq = magnitude_sq(ab)

    if ab_mag_sq == 0: # A and B are the same point
        return a

    # Project P onto the line defined by AB, but clamp t to [0, 1]
    t = dot_product(ap, ab) / ab_mag_sq
    t = max(0, min(1, t)) # Clamp t to be on the segment

    closest_point = (a[0] + t * ab[0], a[1] + t * ab[1])
    return closest_point

def check_circle_square_collision(circle_world_pos_x, circle_world_pos_y, circle_radius, square_world_verts: list[tuple[float, float]]) -> bool:
    """
    Checks collision between a circle and a square (defined by its world vertices).
    This method finds the closest point on the square's perimeter to the circle's center.
    """
    circle_center = (circle_world_pos_x, circle_world_pos_y)
    closest_point_overall = None
    min_dist_sq_overall = float('inf')

    # 1. Check if circle center is inside the square (using SAT concept lightly)
    #    If it is, they are colliding.
    is_inside = True
    axes = get_axes(square_world_verts)
    for axis in axes:
        min_proj_sq, max_proj_sq = project_polygon(axis, square_world_verts)
        circle_proj = dot_product(circle_center, axis)
        if not (min_proj_sq <= circle_proj <= max_proj_sq):
            # For a convex polygon, if the center projected is outside any projection, it's outside.
            # However, we need to be careful. A better check for point in polygon is needed if we rely solely on this.
            # Let's refine: check if circle_proj is within square_proj +/- radius on that axis.
            # This is more like checking if the circle's projection overlaps the square's.
            if circle_proj + circle_radius < min_proj_sq or circle_proj - circle_radius > max_proj_sq:
                is_inside = False # Potentially separated by this axis if we only consider center
                # break # Don't break yet, test all axes for containment.
                # Actually, if the circle's *projection* doesn't overlap, they can't collide. This is SAT vs circle.
                # Project circle onto axis: [center_proj - radius, center_proj + radius]
                min_proj_circle = circle_proj - circle_radius
                max_proj_circle = circle_proj + circle_radius
                if max_proj_circle < min_proj_sq or max_proj_sq < min_proj_circle:
                    return False # Separated by this axis
    # If we passed all axes for SAT (circle vs polygon), they are colliding.
    # The axes for circle vs polygon SAT are the polygon's normals + axes from circle center to polygon vertices.
    # The above check is a simplified SAT (polygon normals only). A full SAT is more robust.
    # For now, let's rely on closest point for edges and vertices.
    # An alternative: if after checking all polygon axes, no separation found, THEN check axes from circle center to vertices.

    # 2. If not clearly separated by SAT on square's axes, check distance to edges/vertices.
    # Find the closest point on each edge of the square to the circle's center.
    for i in range(len(square_world_verts)):
        p1 = square_world_verts[i]
        p2 = square_world_verts[(i + 1) % len(square_world_verts)] # Next vertex, wraps around
        
        closest_pt_on_segment = get_closest_point_on_segment(circle_center, p1, p2)
        dist_sq = magnitude_sq(subtract_vectors(circle_center, closest_pt_on_segment))
        
        if dist_sq < min_dist_sq_overall:
            min_dist_sq_overall = dist_sq
            # closest_point_overall = closest_pt_on_segment # Not strictly needed for bool check

    # If the minimum squared distance is less than or equal to radius squared, they collide.
    if min_dist_sq_overall <= circle_radius**2:
        return True

    # 3. Final check: if the circle center is inside the polygon (if min_dist_sq_overall is misleading for this case).
    # A point-in-polygon test (e.g., ray casting or winding number) would be robust here.
    # However, if the closest point on any edge is > radius away, and the SAT checks above didn't confirm collision,
    # they should be separate, unless the circle is *entirely* inside the square without touching edges.
    # The simplified SAT above (projecting circle as a line segment on square axes) should handle containment.
    
    # Let's refine the SAT part for circle-polygon for better containment check.
    all_axes_to_check = get_axes(square_world_verts)
    # Also need axes from circle center to polygon vertices for full circle-polygon SAT
    for vertex in square_world_verts:
        axis_to_vertex = normalize_vector(subtract_vectors(vertex, circle_center))
        if (axis_to_vertex[0] !=0 or axis_to_vertex[1] !=0):
            # Avoid duplicate axes check similar to get_axes
            is_duplicate = False
            for ax_exist in all_axes_to_check:
                if abs(dot_product(ax_exist, axis_to_vertex) - 1.0) < 1e-6 or \
                   abs(dot_product(ax_exist, axis_to_vertex) + 1.0) < 1e-6:
                    is_duplicate = True
                    break
            if not is_duplicate:
                all_axes_to_check.append(axis_to_vertex)

    for axis in all_axes_to_check:
        min_sq, max_sq = project_polygon(axis, square_world_verts)
        circle_center_proj = dot_product(circle_center, axis)
        min_circle_proj = circle_center_proj - circle_radius
        max_circle_proj = circle_center_proj + circle_radius

        if max_circle_proj < min_sq or max_sq < min_circle_proj:
            return False # Found a separating axis

    return True # No separating axis found by full SAT, collision

def get_square_vertices(center_x, center_y, width, height, angle_degrees) -> list[tuple[float, float]]:
    """Calculates the world coordinates of a square's vertices given its center, size, and rotation."""
    angle_rad = math.radians(angle_degrees)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    
    half_w = width / 2
    half_h = height / 2
    
    # Local coordinates of corners relative to center
    local_corners = [
        (-half_w, -half_h),
        ( half_w, -half_h),
        ( half_w,  half_h),
        (-half_w,  half_h)
    ]
    
    world_corners = []
    for x, y in local_corners:
        # Rotate
        rotated_x = x * cos_a - y * sin_a
        rotated_y = x * sin_a + y * cos_a
        # Translate to world position
        world_corners.append((center_x + rotated_x, center_y + rotated_y))
    return world_corners 