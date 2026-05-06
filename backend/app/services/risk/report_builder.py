from __future__ import annotations

from typing import Any


def build_risk_report(base_result: dict[str, Any], rainfall_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    risk_index = base_result.get("risk_index")
    summary_risk_index = rainfall_summary.get("max_case", {}).get("risk_index") if rainfall_summary else None
    report_risk_index = max(
        [value for value in (risk_index, summary_risk_index) if isinstance(value, (int, float))],
        default=risk_index,
    )
    max_abs_stress = base_result.get("max_abs_stress")
    stress_limit_pa = base_result.get("stress_limit_pa") or 315_000_000.0
    risk_level = _risk_level(report_risk_index)

    if max_abs_stress is None:
        description = "有限元计算未提取到有效最大应力，需检查 h5 结果与求解日志。"
    elif risk_index is not None and risk_index >= 1:
        description = (
            f"当前基础工况最大应力约 {max_abs_stress / 1_000_000:.2f} MPa，"
            f"已超过 {stress_limit_pa / 1_000_000:.0f} MPa 控制阈值，存在结构失稳风险。"
        )
    else:
        description = (
            f"当前基础工况最大应力约 {max_abs_stress / 1_000_000:.2f} MPa，"
            f"未超过 {stress_limit_pa / 1_000_000:.0f} MPa 控制阈值。"
        )

    return {
        "risk_level": risk_level,
        "risk_index": report_risk_index,
        "description": description,
        "collapse_prediction": _collapse_prediction(report_risk_index, rainfall_summary),
        "recommendation": _recommendation(report_risk_index),
    }


def _risk_level(risk_index: float | None) -> str:
    if risk_index is None:
        return "待复核"
    if risk_index >= 1:
        return "高风险"
    if risk_index >= 0.8:
        return "中风险"
    if risk_index >= 0.5:
        return "关注"
    return "低风险"


def _collapse_prediction(risk_index: float | None, rainfall_summary: dict[str, Any] | None = None) -> str:
    damage_text = rainfall_summary.get("damage_conclusions_text") if rainfall_summary else ""
    if damage_text and damage_text != "无":
        return f"完整降雨工况计算显示：{damage_text}，将发生倒坍或达到失稳判据。"

    max_case = rainfall_summary.get("max_case") if rainfall_summary else None
    if max_case and max_case.get("rainfall_mm") is not None and max_case.get("day") is not None:
        return (
            f"完整降雨工况下暂未达到失稳阈值；最大风险出现在 "
            f"{max_case['rainfall_mm']:g}mm 连续 {max_case['day']}d 工况。"
        )

    if risk_index is None:
        return "当前计算结果不足，暂不能给出倒塌预测。"
    if risk_index >= 1:
        return "若继续遭遇强风、强降雨或地基沉降累积，可能发生倒坍。"
    return "在当前基础工况下暂未达到失稳阈值；完整降雨工况接入后将给出连续降雨倒坍预测。"


def _recommendation(risk_index: float | None) -> str:
    if risk_index is None:
        return "建议复核有限元输入文件、求解日志和 h5 应力结果。"
    if risk_index >= 1:
        return "建议立即安排现场复核、限制周边作业，并开展加固或卸载处置。"
    if risk_index >= 0.8:
        return "建议提高巡检频率，复核塔基沉降和杆件连接状态。"
    return "建议维持常规监测，并在强降雨或大风后复测。"
