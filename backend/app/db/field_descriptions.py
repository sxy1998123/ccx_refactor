from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldDescription:
    table_name: str
    field_name: str
    display_name: str
    data_type: str
    description: str
    display_order: int
    is_required: bool = False
    is_primary_key: bool = False


FIELD_DESCRIPTIONS: tuple[FieldDescription, ...] = (
    FieldDescription("towers", "line_id", "线路号", "TEXT", "输电线路编号，用于归档本次杆塔采集与分析结果。", 1, True),
    FieldDescription("towers", "longitude", "经度", "REAL", "杆塔位置经度，WGS84 坐标。", 2),
    FieldDescription("towers", "latitude", "纬度", "REAL", "杆塔位置纬度，WGS84 坐标。", 3),
    FieldDescription("towers", "height_m", "高度", "REAL", "杆塔高度，单位米。", 4),
    FieldDescription("towers", "tower_type", "杆塔种类", "TEXT", "杆塔种类，例如直线塔、耐张塔、终端塔。", 5),
    FieldDescription("towers", "material", "杆塔材料", "TEXT", "杆塔主要材料，例如角钢、钢管、混凝土。", 6),
    FieldDescription("towers", "risk_level", "风险等级", "TEXT", "杆塔综合风险等级，例如常规、关注、中风险、高风险。", 7),
    FieldDescription("towers", "collected_at", "采集时间", "TEXT", "杆塔数据采集时间，ISO 8601 字符串。", 8),
    FieldDescription("towers", "created_at", "记录创建时间", "TEXT", "数据库记录创建时间。", 9, True),
    FieldDescription("towers", "updated_at", "记录修改时间", "TEXT", "数据库记录最后修改时间。", 10, True),
    FieldDescription("towers", "example1", "图片1", "TEXT", "杆塔图片 1，保存图片路径、相对 URL 或资源 key。", 11),
    FieldDescription("towers", "example2", "图片2", "TEXT", "杆塔图片 2，保存图片路径、相对 URL 或资源 key。", 12),
    FieldDescription("towers", "example3", "图片3", "TEXT", "杆塔图片 3，保存图片路径、相对 URL 或资源 key。", 13),
    FieldDescription("towers", "example4", "图片4", "TEXT", "杆塔图片 4，保存图片路径、相对 URL 或资源 key。", 14),
    FieldDescription("towers", "example5", "图片5", "TEXT", "杆塔图片 5，保存图片路径、相对 URL 或资源 key。", 15),
    FieldDescription("geology_records", "disaster_type", "灾害类型", "TEXT", "历史地质灾害类型，按字符串保存。", 1),
    FieldDescription("geology_records", "longitude", "经度", "TEXT", "历史地质灾害记录经度，按字符串保存。", 2),
    FieldDescription("geology_records", "latitude", "纬度", "TEXT", "历史地质灾害记录纬度，按字符串保存。", 3),
    FieldDescription("geology_records", "clay_content_percent", "黏粒含量（%）", "REAL", "历史地质灾害指标 D 列，本次预处理生成的黏粒含量。", 4),
    FieldDescription("geology_records", "silt_content_percent", "粉粒含量（%）", "REAL", "历史地质灾害指标 E 列，本次预处理生成的粉粒含量。", 5),
    FieldDescription("geology_records", "sand_content_percent", "砂粒含量（%）", "REAL", "历史地质灾害指标 F 列，本次预处理生成的砂粒含量。", 6),
    FieldDescription("geology_records", "soil_moisture_percent", "土壤含水率（%）", "REAL", "历史地质灾害指标 G 列，本次预处理生成的土壤含水率。", 7),
    FieldDescription("geology_records", "porosity_percent", "孔隙度（%）", "REAL", "历史地质灾害指标 H 列，本次预处理生成的孔隙度。", 8),
    FieldDescription("geology_records", "permeability_mm_h", "渗透系数（mm/h）", "REAL", "历史地质灾害指标 I 列，本次预处理生成的渗透系数。", 9),
    FieldDescription("geology_records", "cohesion_kpa", "黏聚力（kPa）", "REAL", "历史地质灾害指标 J 列，本次预处理生成的黏聚力。", 10),
    FieldDescription("geology_records", "soil_thickness_m", "土层厚度（m）", "REAL", "历史地质灾害指标 K 列，本次预处理生成的土层厚度。", 11),
    FieldDescription("geology_records", "bedrock_depth_m", "基岩埋深（m）", "REAL", "历史地质灾害指标 L 列，本次预处理生成的基岩埋深。", 12),
    FieldDescription("geology_records", "slope_degree", "坡度（°）", "REAL", "历史地质灾害指标 M 列，本次预处理生成的坡度。", 13),
    FieldDescription("geology_records", "aspect_degree", "坡向（°）", "REAL", "历史地质灾害指标 N 列，本次预处理生成的坡向。", 14),
    FieldDescription("geology_records", "relative_relief_m", "相对高差（m）", "REAL", "历史地质灾害指标 O 列，本次预处理生成的相对高差。", 15),
    FieldDescription("geology_records", "terrain_relief_m_per_km2", "地形起伏度（m/km²）", "REAL", "历史地质灾害指标 P 列，本次预处理生成的地形起伏度。", 16),
    FieldDescription("geology_records", "twi", "地形湿度指数（TWI）", "REAL", "历史地质灾害指标 Q 列，本次预处理生成的地形湿度指数。", 17),
    FieldDescription("geology_records", "tri", "地形粗糙度指数（TRI）", "REAL", "历史地质灾害指标 R 列，本次预处理生成的地形粗糙度指数。", 18),
    FieldDescription("geology_records", "ndvi", "NDVI", "REAL", "历史地质灾害指标 S 列，本次预处理生成的 NDVI。", 19),
    FieldDescription("geology_records", "vegetation_coverage_percent", "植被覆盖度（%）", "REAL", "历史地质灾害指标 T 列，本次预处理生成的植被覆盖度。", 20),
    FieldDescription("geology_records", "lai_m2_m2", "LAI叶面积指数（m²/m²）", "REAL", "历史地质灾害指标 U 列，本次预处理生成的 LAI 叶面积指数。", 21),
    FieldDescription("geology_records", "canopy_coverage_percent", "冠层覆盖率（%）", "REAL", "历史地质灾害指标 V 列，本次预处理生成的冠层覆盖率。", 22),
    FieldDescription("geology_records", "created_at", "记录创建时间", "TEXT", "数据库记录创建时间。", 23, True),
    FieldDescription("geology_records", "updated_at", "记录修改时间", "TEXT", "数据库记录最后修改时间。", 24, True),
    FieldDescription("geology_records", "example1", "图片1", "TEXT", "历史地质灾害指标图片 1，保存图片路径、相对 URL 或资源 key。", 25),
    FieldDescription("geology_records", "example2", "图片2", "TEXT", "历史地质灾害指标图片 2，保存图片路径、相对 URL 或资源 key。", 26),
    FieldDescription("geology_records", "example3", "图片3", "TEXT", "历史地质灾害指标图片 3，保存图片路径、相对 URL 或资源 key。", 27),
    FieldDescription("geology_records", "example4", "图片4", "TEXT", "历史地质灾害指标图片 4，保存图片路径、相对 URL 或资源 key。", 28),
    FieldDescription("geology_records", "example5", "图片5", "TEXT", "历史地质灾害指标图片 5，保存图片路径、相对 URL 或资源 key。", 29),
)
