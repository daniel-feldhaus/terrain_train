import geopandas as gpd
import folium
from shapely.geometry import MultiPoint, Polygon, MultiPolygon
from alphashape import alphashape
from tqdm import tqdm


def get_coast_data(resolution="h"):
    file_path = f"./GSHHS_{resolution}_L1.shp"
    print("Reading shp file")
    gdf = gpd.read_file(file_path)
    print("Converting to CRS")
    gdf = gdf.to_crs(epsg=3395)  # Use a CRS suitable for area calculations
    print("Calculating areas")
    gdf["area_km2"] = gdf["geometry"].area / 10**6  # Convert area to square kilometers
    return gdf


def filter_polygons_by_area(gdf, min_area, max_area):
    return gdf[(gdf["area_km2"] >= min_area) & (gdf["area_km2"] <= max_area)]


def calculate_centroids(gdf):
    gdf_proj = gdf.to_crs(epsg=3395)  # Use a suitable projected CRS (e.g., EPSG:3395)
    centroids = MultiPoint(list(gdf_proj.centroid))
    return gpd.GeoSeries(centroids, crs=gdf_proj.crs).to_crs(epsg=4326)


def create_encompassing_polygon(centroids, excluded_polygons):
    polygon = centroids.unary_union.convex_hull
    for excluded_polygon in tqdm(
        excluded_polygons, total=len(excluded_polygons), desc="Removing landmasses"
    ):
        polygon = polygon.difference(excluded_polygon)
    return polygon


def close_holes(polygon):
    if isinstance(polygon, MultiPolygon):
        polygons = [Polygon(p.exterior) for p in polygon.geoms]
        return MultiPolygon(polygons)
    else:
        return Polygon(polygon.exterior)


def simplify_polygon(polygon, tolerance):
    return polygon.simplify(tolerance=tolerance, preserve_topology=True)


def save_polygon_to_shapefile(polygon, output_path, crs):
    output_gdf = gpd.GeoDataFrame(geometry=[polygon], crs=crs)
    output_gdf.to_file(output_path, driver="ESRI Shapefile")
    print(f"Polygon saved to: {output_path}")


def plot_shapes_with_centroids(gdf, output_path):
    m = folium.Map(location=[20, 0], zoom_start=2, tiles="cartodbpositron")
    for _, row in gdf.iterrows():
        simplified_geom = row["geometry"].simplify(tolerance=0.01, preserve_topology=True)
        geo_j = folium.GeoJson(
            data=simplified_geom.__geo_interface__,
            style_function=lambda x: {"color": "blue", "weight": 2, "fillColor": "blue"},
        )
        geo_j.add_to(m)
        centroid = row["geometry"].centroid
        folium.Marker([centroid.y, centroid.x], icon=folium.Icon(color="red")).add_to(m)
    m.save(output_path)


def main():
    gdf = get_coast_data("i")
    min_area = 300
    max_area = 10000
    alpha = 0.1  # Adjust this value to control the tightness of the shape

    filtered_polygons = filter_polygons_by_area(gdf, min_area, max_area)
    centroids = calculate_centroids(filtered_polygons)

    alpha_shape = alphashape(centroids, alpha)
    simplified_polygon = simplify_polygon(alpha_shape, tolerance=0.01)

    save_polygon_to_shapefile(simplified_polygon, "islands_alpha_shape.shp", filtered_polygons.crs)
    plot_shapes_with_centroids(filtered_polygons, "map_with_shapes.html")
    plot_shapes_with_centroids(
        gpd.GeoDataFrame(geometry=[simplified_polygon], crs=filtered_polygons.crs),
        "map_bounds.html",
    )


if __name__ == "__main__":
    main()
