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
    FieldDescription("geology_records", "humidity_percent", "湿度", "REAL", "采样窗口中的环境湿度，单位百分比。", 1),
    FieldDescription("geology_records", "illumination_lux", "光照", "REAL", "采样窗口中的光照强度，单位 Lux。", 2),
    FieldDescription("geology_records", "pressure_kpa", "气压", "REAL", "采样窗口中的环境气压，单位 kPa。", 3),
    FieldDescription("geology_records", "rainfall_mm", "环境降雨量", "REAL", "采样窗口中的环境降雨量，单位毫米。", 4),
    FieldDescription("geology_records", "temperature_c", "环境温度", "REAL", "采样窗口中的环境温度，单位摄氏度。", 5),
    FieldDescription("geology_records", "wind_direction_deg", "环境风向", "REAL", "采样窗口中的环境风向，单位度。", 6),
    FieldDescription("geology_records", "wind_speed_mps", "风速", "REAL", "采样窗口中的环境风速，单位米每秒。", 7),
    FieldDescription("geology_records", "soil_moisture_percent", "土壤湿度", "REAL", "采样窗口中的土壤湿度，单位百分比。", 8),
    FieldDescription("geology_records", "soil_temperature_c", "土壤温度", "REAL", "采样窗口中的土壤温度，单位摄氏度。", 9),
    FieldDescription("geology_records", "collected_at", "采集时间", "TEXT", "地质与环境采样时间，ISO 8601 字符串。", 10),
    FieldDescription("geology_records", "created_at", "记录创建时间", "TEXT", "数据库记录创建时间。", 11, True),
    FieldDescription("geology_records", "updated_at", "记录修改时间", "TEXT", "数据库记录最后修改时间。", 12, True),
    FieldDescription("geology_records", "example1", "图片1", "TEXT", "地质记录图片 1，保存图片路径、相对 URL 或资源 key。", 13),
    FieldDescription("geology_records", "example2", "图片2", "TEXT", "地质记录图片 2，保存图片路径、相对 URL 或资源 key。", 14),
    FieldDescription("geology_records", "example3", "图片3", "TEXT", "地质记录图片 3，保存图片路径、相对 URL 或资源 key。", 15),
    FieldDescription("geology_records", "example4", "图片4", "TEXT", "地质记录图片 4，保存图片路径、相对 URL 或资源 key。", 16),
    FieldDescription("geology_records", "example5", "图片5", "TEXT", "地质记录图片 5，保存图片路径、相对 URL 或资源 key。", 17),
)
