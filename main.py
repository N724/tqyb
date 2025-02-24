import aiohttp
import re
import logging
from typing import Optional
from astrbot.api.all import AstrMessageEvent, CommandResult, Context, Plain
import astrbot.api.event.filter as filter
from astrbot.api.star import register, Star

logger = logging.getLogger("astrbot")

@register("smart_weather", "nbx", "智能天气插件", "3.1.0")
class WeatherStar(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.api_url = "https://xiaoapi.cn/API/tq.php"
        self.timeout = aiohttp.ClientTimeout(total=10)
        self.headers = {"User-Agent": "AstrBot/WeatherPlugin"}
        self.location_cache = {}

    def _extract_location(self, text: str) -> Optional[str]:
        """智能地点提取引擎"""
        try:
            # 清理干扰符号
            clean_text = re.sub(r"[@#【】$$$$()（）]", "", text).strip()
            
            # 匹配多种格式模式
            patterns = [
                r"^(?:天气|查天气)?\s*([\u4e00-\u9fa5]{2,8}?)(?:天气|的天气)?$",  # 北京天气 / 天气北京
                r"^(.+?)(?:的?天气|天气情况)$",  # 北京的天气 / 广州天气情况
                r"^([\u4e00-\u9fa5]{2,8})$"  # 纯地名
            ]
            
            for pattern in patterns:
                if match := re.fullmatch(pattern, clean_text):
                    location = match.group(1)
                    if location in ["天气", "查天气"]:  # 过滤无效匹配
                        continue
                    return location
            return None
        except Exception as e:
            logger.error(f"地点提取失败: {str(e)}")
            return None

    async def _fetch_weather(self, location: str) -> Optional[str]:
        """获取天气数据（带缓存）"""
        try:
            # 检查缓存（5分钟有效期）
            if cached := self.location_cache.get(location):
                if time.time() - cached["timestamp"] < 300:
                    return cached["data"]
            
            async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as session:
                async with session.get(self.api_url, params={"msg": location}) as resp:
                    if resp.status == 200:
                        data = await resp.text(encoding='utf-8')
                        self.location_cache[location] = {
                            "timestamp": time.time(),
                            "data": data
                        }
                        return data
                    logger.error(f"API请求失败 HTTP {resp.status}")
        except Exception as e:
            logger.error(f"网络请求异常: {str(e)}")
        return None

    def _parse_weather_data(self, raw_data: str) -> dict:
        """增强版数据解析"""
        parsed = {
            "location": "未知地区",
            "temp": "N/A",
            "feel_temp": "N/A",
            "humidity": "N/A",
            "warnings": []
        }
        
        try:
            # 基础信息解析
            if match := re.search(
                r"^(.+?)\s+温度：([\d.-]+)℃\s+"
                r"体感：([\d.-]+)℃\s+"
                r"湿度：(\d+)%", 
                raw_data
            ):
                parsed.update({
                    "location": match.group(1).split()[-1],
                    "temp": match.group(2),
                    "feel_temp": match.group(3),
                    "humidity": match.group(4)
                })
            
            # 天气预警解析
            if warnings := re.findall(r"【预警中】(.*?（数据来源：.*?）)", raw_data):
                parsed["warnings"] = warnings
                
            # 降雨信息解析
            if rain_info := re.search(r"您(.*?)正在下(.*?)，", raw_data):
                parsed["rain"] = f"{rain_info.group(1)}{rain_info.group(2)}"
            
            return parsed
        except Exception as e:
            logger.error(f"数据解析异常: {str(e)}")
            return parsed

    def _build_response(self, data: dict) -> str:
        """构建响应消息"""
        msg = [
            f"🌏【{data['location']}实时天气】",
            f"🌡️ 温度：{data['temp']}℃（体感{data['feel_temp']}℃）",
            f"💧 湿度：{data['humidity']}%"
        ]
        
        if 'rain' in data:
            msg.append(f"🌧️ 周边降水：{data['rain']}")
            
        if data["warnings"]:
            msg.append("\n🚨 气象预警：")
            msg.extend([f"• {w}" for w in data["warnings"]])
            
        msg.append("\n📡 数据来源：中国气象局")
        return "\n".join(msg)

    @filter.command(".*")  # 匹配所有消息
    async def smart_weather(self, event: AstrMessageEvent):
        """智能天气查询"""
        try:
            # 获取原始消息内容
            raw_text = getattr(event, 'content', '').strip()
            if not raw_text:
                return
                
            # 提取地点
            if not (location := self._extract_location(raw_text)):
                return
                
            logger.info(f"识别到天气查询地点：{location}")
            
            # 发送等待提示
            yield CommandResult().message(f"⛅ 正在获取【{location}】的天气...")
            
            # 获取天气数据
            if raw_data := await self._fetch_weather(location):
                weather_data = self._parse_weather_data(raw_data)
                if weather_data["temp"] == "N/A":
                    yield CommandResult().error("⚠️ 天气数据解析失败，请尝试简化地点名称")
                    return
                    
                yield CommandResult().message(self._build_response(weather_data))
            else:
                yield CommandResult().error("🌩️ 天气服务暂时不可用，请稍后再试")
                
        except Exception as e:
            logger.error(f"处理异常: {str(e)}", exc_info=True)
            yield CommandResult().error("⚡ 系统开小差啦，请联系管理员")

# 配套文件
