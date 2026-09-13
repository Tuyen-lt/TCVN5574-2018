from tcvn5574 import RebarGroup


def grp(*layers):
    """RebarGroup from (n_bars, diameter, distance_from_edge) tuples."""
    g = RebarGroup()
    for n, d, a in layers:
        g.add_layer(n, d, a)
    return g
