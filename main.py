import aiohttp
import re
import logging
from typing import Optional
from astrbot.api.all import AstrMessageEvent, CommandResult, Context, Plain
import astrbot.api.event.filter as filter
from astrbot.api.star import register, Star

logger = logging.getLogger("astrbot")

@register("weather_report", "nbx", "全平台天气插件", "2.0.1")
class WeatherStar(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.api_url = "https://xiaoapi.cn/API/tq.php"
        self.timeout = aiohttp.ClientTimeout(total=10)
        self.headers = {"User-Agent": "AstrBot/WeatherPlugin"}

    def _parse_command_args(self, event) -> list:
        """增强版多平台参数解析"""
        try:
            raw_content = getattr(event, 'content', '').strip()
            logger.debug(f"原始消息内容: {raw_content}")

            # 微信平台专用解析
            if hasattr(event, 'content') and 'wechat' in str(self.context.platform).lower():
                # 匹配以下格式：
                # 1. @机器人 天气 北京朝阳
                # 2. 天气 毕节
                # 3. 查天气 贵阳
                match = re.match(
                    r"^(?:@\S+\s+)?(?:天气|查天气)[\s　]*([\u4e00-\u9fa5]+)$",
                    raw_content
                )
                if match:
                    logger.debug(f"成功匹配参数: {match.group(1)}")
                    return [match.group(1)]
                return []

            # 其他平台处理
            return getattr(event, 'args', [])
        except Exception as e:
            logger.error(f"参数解析失败: {str(e)}")
            return []

    async def _fetch_weather(self, location: str) -> Optional[str]:
        """获取天气数据"""
        try:
            async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as session:
                async with session.get(self.api_url, params={"msg": location}) as resp:
                    if resp.status == 200:
                        return await resp.text(encoding='utf-8')
                    logger.error(f"API异常 HTTP {resp.status}")
        except Exception as e:
            logger.error(f"请求失败: {str(e)}")
        return None

    def _parse_weather_data(self, raw_data: str) -> dict:
        """解析天气数据"""
        parsed = {"location": "未知地区"}
        try:
            # 基础信息解析
            if match := re.search(r"(.+?)\s+温度：([\d.-]+)℃", raw_data):
                parsed["location"] = match.group(1).split()[-1]
                parsed["temp"] = match.group(2)
            
            # 体感温度
            if feel_match := re.search(r"体感：([\d.-]+)℃", raw_data):
                parsed["feel_temp"] = feel_match.group(1)
            
            # 其他字段解析...
            return parsed
        except Exception as e:
            logger.error(f"数据解析异常: {str(e)}")
            return parsed

    @filter.command("天气", "查天气")
    async def get_weather(self, event: AstrMessageEvent):
        '''微信/QQ全平台天气查询'''
        try:
            # 参数解析
            args = self._parse_command_args(event)
            logger.debug(f"解析后参数: {args}")
            
            if not args:
                yield CommandResult().error(
                    "📍 请输入有效地点名称\n"
                    "示例：\n"
                    "微信：@机器人 天气 北京朝阳\n"
                    "其他：/天气 上海浦东"
                )
                return

            location = args
            yield CommandResult().message(f"⛅ 正在获取【{location}】的天气...")

            if raw_data := await self._fetch_weather(location):
                weather_data = self._parse_weather_data(raw_data)
                response = (
                    f"🌏【{weather_data['location']}天气速报】\n"
                    f"🌡️ 当前温度：{weather_data.get('temp', 'N/A')}℃\n"
                    f"🤒 体感温度：{weather_data.get('feel_temp', 'N/A')}℃\n"
                    "📡 数据来自中国气象局"
                )
                yield CommandResult().message(response)
            else:
                yield CommandResult().error("服务暂时不可用，请稍后重试")

        except Exception as e:
            logger.error(f"处理异常: {str(e)}", exc_info=True)
            yield CommandResult().error("天气服务暂时不可用")

# 以下为配套文件
