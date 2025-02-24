import aiohttp
import re
import logging
from typing import Optional
from astrbot.api.all import AstrMessageEvent, CommandResult, Context, Plain
import astrbot.api.event.filter as filter
from astrbot.api.star import register, Star

logger = logging.getLogger("astrbot")

@register("free_weather", "nbx", "自由格式天气插件", "3.2.0")
class WeatherPlugin(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.api_url = "https://xiaoapi.cn/API/zs_tq.php"
        self.timeout = aiohttp.ClientTimeout(total=15)
        self.weather_pattern = re.compile(
            r"^(?:天气|查天气)?[ 　]*([\u4e00-\u9fa5]{2,20}?)(?:天气|的天气)?$"
        )

    def _extract_location(self, text: str) -> Optional[str]:
        """智能提取地点"""
        # 清理特殊符号
        clean_text = re.sub(r"[@#【】]", "", text.strip())
        
        # 匹配纯中文地点
        if re.fullmatch(r"[\u4e00-\u9fa5]+", clean_text):
            return clean_text
        
        # 匹配天气相关格式
        if match := self.weather_pattern.match(clean_text):
            return match.group(1)
        
        return None

    async def fetch_weather(self, location: str) -> Optional[dict]:
        """获取天气数据"""
        try:
            params = {
                "type": "cytq",
                "msg": location,
                "n": "1"
            }
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(self.api_url, params=params) as resp:
                    if resp.status != 200:
                        logger.error(f"API错误 HTTP {resp.status}")
                        return None
                    return await resp.json()
        except Exception as e:
            logger.error(f"请求失败: {str(e)}")
            return None

    def _build_message(self, data: dict) -> str:
        """构建消息内容"""
        msg = [
            f"🌦 彩云天气 - {data.get('name', '未知地区')}",
            "━" * 20
        ]
        
        if weather_data := data.get("data"):
            # 解析原始数据
            for line in weather_data.split("\n"):
                if "：" in line:
                    key, value = line.split("：", 1)
                    msg.append(f"▫️ {key.strip()}：{value.strip()}")
        
        if time_str := data.get("time"):
            msg.append(f"\n⏱ 数据时间：{time_str.split('.')}")
            
        return "\n".join(msg)

    @filter.command(".*")  # 匹配所有消息
    async def auto_weather(self, event: AstrMessageEvent):
        """自动响应天气查询"""
        try:
            raw_text = event.message_str.strip()
            if not raw_text:
                return
                
            # 提取地点
            location = self._extract_location(raw_text)
            if not location:
                return
                
            logger.info(f"识别到查询地点：{location}")
            
            # 发送等待提示
            yield CommandResult().message(f"⏳ 正在获取 {location} 的天气...")
            
            # 获取数据
            data = await self.fetch_weather(location)
            if not data or data.get("code") != 200:
                yield CommandResult().error("⚠️ 天气数据获取失败")
                return
                
            yield CommandResult().message(self._build_message(data)).use_t2i(False)

        except Exception as e:
            logger.error(f"处理异常: {str(e)}", exc_info=True)
            yield CommandResult().error("💥 服务暂时不可用")

    @filter.command("天气帮助")
    async def weather_help(self, event: AstrMessageEvent):
        """新版帮助信息"""
        help_msg = [
            "🌦 自由格式天气查询",
            "支持以下任意格式：",
            "1. 直接发送地名（例：北京）",
            "2. 地名+天气（例：上海天气）",
            "3. 天气+地名（例：天气广州）",
            "4. 的天气格式（例：深圳的天气）",
            "━" * 20,
            "遇到问题请联系管理员"
        ]
        yield CommandResult().message("\n".join(help_msg))
