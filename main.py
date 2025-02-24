import aiohttp
import logging
import re
from typing import Optional, Dict, List
from astrbot.api.all import AstrMessageEvent, CommandResult, Context, Plain
import astrbot.api.event.filter as filter
from astrbot.api.star import register, Star

logger = logging.getLogger("astrbot")

@register("weather", "作者名", "精准天气查询插件", "2.0.1")
class WeatherPlugin(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.api_url = "https://xiaoapi.cn/API/tq.php"
        self.timeout = aiohttp.ClientTimeout(total=15)

    async def fetch_weather(self, location: str) -> Optional[Dict[str, str]]:
        """获取天气数据"""
        try:
            params = {"msg": location, "n": "1"}
            logger.debug(f"请求参数：{params}")
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(self.api_url, params=params) as resp:
                    if resp.status != 200:
                        logger.error(f"API请求失败 HTTP {resp.status}")
                        return None

                    raw_text = await resp.text()
                    logger.debug(f"API原始响应:\n{raw_text}")
                    return self._parse_weather_text(raw_text)

        except aiohttp.ClientError as e:
            logger.error(f"网络请求异常: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"未知异常: {str(e)}", exc_info=True)
            return None

    def _parse_weather_text(self, text: str) -> Dict[str, str]:
        """稳健的天气数据解析"""
        result = {"location": "未知地区"}
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        
        if len(lines) < 2:
            return {"error": "无效的天气数据格式"}

        try:
            # 解析地理位置（处理列表格式）
            first_line = lines
            if first_line.startswith('[') and first_line.endswith(']'):
                locations = first_line[1:-1].replace("'", "").split(", ")
                result["location"] = locations if locations else "未知地区"
                logger.debug(f"解析到多个候选地址：{locations}")
            else:
                result["location"] = first_line
        except Exception as e:
            logger.error(f"地理位置解析失败: {str(e)}")

        # 解析天气数据
        current_key = None
        for line in lines[1:]:
            line = re.sub(r"[，。！!]+$", "", line)  # 清理结尾标点
            
            # 处理多行预警信息
            if line.startswith("预警信息："):
                result["预警信息"] = line[5:]
                current_key = "预警信息"
            elif line.startswith("【"):
                result["预警信息"] = line
                current_key = None
            # 处理降水提示
            elif "正在下" in line and ("转" in line or "后转" in line):
                result["降水提示"] = re.sub(r"您(\S+方向)", r"📍\1", line)
                current_key = None
            # 解析键值对数据
            elif "：" in line:
                key, value = line.split("：", 1)
                key = key.strip().replace("pm2.5", "PM2.5")
                result[key] = value.strip()
                current_key = key
            # 合并多行内容
            elif current_key:
                result[current_key] += "\n" + line

        return result

    def _format_message(self, data: Dict[str, str]) -> List[str]:
        """生成美观的天气报告"""
        msg = [
            f"📍 地区：{data.get('location', '未知地区')}",
            "━" * 25
        ]

        # 核心天气指标
        weather_indicators = [
            ("🌡️ 温度", "温度"),
            ("👤 体感", "体感"),
            ("💧 湿度", "湿度"),
            ("👓 能见度", "能见度"),
            ("🛡️ PM2.5", "PM2.5"),
            ("🏭 空气质量", "空气质量"),
            ("☀️ 紫外线", "紫外线强度"),
            ("📌 体感描述", "总体感觉")
        ]
        
        # 添加天气数据
        for display_name, data_key in weather_indicators:
            if value := data.get(data_key):
                msg.append(f"{display_name}：{value}")

        # 降水提示处理
        if rain_info := data.get("降水提示"):
            msg.extend([
                "",
                "🌧️ 降水提示：",
                f"▸ {rain_info.replace('哦，', '').replace('今天', '⏱ 今天')}"
            ])

        # 预警信息处理
        if warning_info := data.get("预警信息"):
            msg.extend([
                "",
                "⚠️ 气象预警：",
                f"🔴 {warning_info.replace('（数据来源：国家预警信息发布中心）', '')}"
            ])

        # 添加数据来源
        msg.append("\n⏱ 数据更新：实时气象数据")
        return msg

    @filter.command("天气")
    async def weather_query(self, event: AstrMessageEvent):
        '''查询精准天气，支持街道级查询'''
        try:
            # 解析指令参数
            args = event.message_str.split(maxsplit=1)
            if len(args) < 2:
                yield CommandResult().error("❌ 请提供查询地址\n示例：/天气 贵阳观山湖区宾阳大道")
                return

            location = args.strip()
            logger.info(f"正在查询 [{location}] 的天气...")

            # 发送查询提示
            yield CommandResult().message(f"🛰 正在获取【{location}】的实时天气...")

            # 获取天气数据
            data = await self.fetch_weather(location)
            if not data or "error" in data:
                logger.warning(f"天气查询失败: {data.get('error', '未知错误')}")
                yield CommandResult().error("⚠️ 数据获取失败，请检查地址格式\n（建议尝试：市+区+街道组合）")
                return

            # 生成并返回天气报告
            formatted_msg = self._format_message(data)
            yield CommandResult().message("\n".join(formatted_msg))

        except Exception as e:
            logger.error(f"指令处理异常: {str(e)}", exc_info=True)
            yield CommandResult().error("🌀 天气服务暂时不可用，请稍后重试")

    @filter.command("天气帮助")
    async def weather_help(self, event: AstrMessageEvent):
        """显示帮助信息"""
        help_msg = [
            "🌦 天气帮助文档",
            "━" * 25,
            "1. 查询指令：",
            "   /天气 <详细地址>",
            "   示例：",
            "   ▸ /天气 杭州西湖区杨公堤",
            "   ▸ /天气 重庆渝中区解放碑步行街",
            "",
            "2. 功能特性：",
            "   ▸ 街道级精准定位",
            "   ▸ 实时温度/湿度/体感",
            "   ▸ 降水预报预警",
            "   ▸ 空气质量监测",
            "",
            "3. 数据说明：",
            "   📍 支持中国大陆地区详细地址查询",
            "   ⏱ 数据每10分钟更新一次",
            "   ⚠️ 预警信息来自国家气象局"
        ]
        yield CommandResult().message("\n".join(help_msg))
