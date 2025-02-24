import aiohttp
import logging
from typing import Optional, Dict
from astrbot.api.all import AstrMessageEvent, CommandResult, Context
import astrbot.api.event.filter as filter
from astrbot.api.star import register, Star

logger = logging.getLogger("astrbot")

@register("weather", "作者名", "趣味天气查询插件", "1.1.0")
class WeatherPlugin(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.api_url = "https://xiaoapi.cn/API/tq.php"
        self.timeout = aiohttp.ClientTimeout(total=15)

    async def fetch_weather(self, location: str) -> Optional[Dict]:
        """获取天气数据（支持街道级查询）"""
        try:
            params = {
                "msg": location.strip(),
                "n": "1"  # 默认选择第一个结果
            }
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(self.api_url, params=params) as resp:
                    if resp.status != 200:
                        logger.error(f"API请求失败 HTTP {resp.status}")
                        return None
                    
                    raw_text = await resp.text()
                    logger.debug(f"API原始响应: {raw_text[:200]}...")
                    return self._parse_weather_data(raw_text)

        except aiohttp.ClientError as e:
            logger.error(f"网络请求异常: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"未知异常: {str(e)}", exc_info=True)
            return None

    def _parse_weather_data(self, raw_data: str) -> Dict:
        """解析文本格式的天气数据"""
        result = {"warnings": [], "rain_alert": ""}
        current_section = None
        
        for line in raw_data.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            # 解析预警信息
            if line.startswith("预警信息："):
                current_section = "warning"
                result["warnings"].append(line[5:])
                continue
                
            # 解析降雨提示
            if "正在下" in line and "哦" in line:
                result["rain_alert"] = line
                continue
                
            # 解析键值对数据
            if "：" in line:
                key, value = line.split("：", 1)
                key = key.strip()
                # 处理多行预警信息
                if current_section == "warning":
                    result["warnings"][-1] += "\n" + line
                else:
                    result[key] = value.strip()
        
        return result

    def _get_weather_emoji(self, temp: str) -> str:
        """根据温度获取趣味表情"""
        try:
            temperature = float(temp.replace("℃", ""))
            if temperature > 30:
                return "🔥"
            elif temperature > 20:
                return "😎"
            elif temperature > 10:
                return "🍂"
            else:
                return "❄️"
        except:
            return "🌡️"

    @filter.command("天气")
    async def weather_query(self, event: AstrMessageEvent):
        '''查询天气，格式：/天气 [地区]'''
        try:
            # 解析参数
            args = event.message_str.split(maxsplit=1)
            if len(args) < 2:
                return CommandResult().error("❌ 请提供查询地点\n示例：/天气 北京朝阳区")
                
            location = args.strip()
            if not location:
                return CommandResult().error("⚠️ 地点不能为空")

            # 发送等待提示
            yield CommandResult().message(f"⏳ 正在侦察 {location} 的天气情况...")

            # 获取天气数据
            data = await self.fetch_weather(location)
            if not data:
                yield CommandResult().error("🌪️ 天气情报获取失败，请稍后再试")
                return

            # 构建响应消息
            msg = []
            
            # 预警信息置顶
            if data.get("warnings"):
                msg.append("🚨【天气预警】🚨")
                msg.extend(data["warnings"])
                msg.append("━" * 20)

            # 基础天气信息
            msg.append(f"🌈 {location} 实时天气")
            
            # 温度相关
            temp_emoji = self._get_weather_emoji(data.get("温度", ""))
            msg.extend([
                f"{temp_emoji} 温度：{data.get('温度', 'N/A')}",
                f"💦 体感温度：{data.get('体感', 'N/A')}",
                f"💧 湿度：{data.get('湿度', 'N/A')}"
            ])

            # 空气质量
            if "空气质量" in data:
                aqi = int(data["空气质量"])
                aqi_emoji = "😷" if aqi > 100 else "😊"
                msg.append(f"{aqi_emoji} 空气质量：{data['空气质量']}")

            # 降雨提示
            if data.get("rain_alert"):
                rain_emoji = "🌧️" if "雨" in data["rain_alert"] else "🌦️"
                msg.append(f"{rain_emoji} {data['rain_alert']}")

            # 紫外线信息
            if "紫外线强度" in data:
                uv_emoji = "☀️" if "强" in data["紫外线强度"] else "⛱️"
                msg.append(f"{uv_emoji} 紫外线：{data['紫外线强度']}")

            # 温馨提示
            if "总体感觉" in data:
                msg.append(f"💡 小贴士：{data['总体感觉']}")

            yield CommandResult().message("\n".join(msg)).use_t2i(False)

        except Exception as e:
            logger.error(f"处理指令异常: {str(e)}", exc_info=True)
            yield CommandResult().error("⚠️ 天气侦察卫星信号中断")

    @filter.command("天气帮助")
    async def weather_help(self, event: AstrMessageEvent):
        """显示帮助信息"""
        help_msg = [
            "🌦️ 天气帮助中心",
            "━" * 20,
            "📌 使用方式：",
            "/天气 <地点> - 查询街道级天气（例如：/天气 上海陆家嘴）",
            "/天气帮助 - 显示本帮助信息",
            "",
            "📌 功能特点：",
            "- 街道级精准预报 🌍",
            "- 实时天气预警 🚨",
            "- 趣味表情互动 😎",
            "- 空气质量监测 🌱",
            "- 降雨提醒服务 🌧️",
            "",
            "📢 注意：支持查询公园、景区等具体地点"
        ]
        yield CommandResult().message("\n".join(help_msg))
