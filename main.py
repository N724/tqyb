import aiohttp
import re
import logging
from typing import Optional
from astrbot.api.all import AstrMessageEvent, CommandResult, Context, Plain
import astrbot.api.event.filter as filter
from astrbot.api.star import register, Star

logger = logging.getLogger("astrbot")

@register("weather_report", "nbx", "全平台天气插件", "2.0.0")
class WeatherStar(Star):
    def __init__(self, context: Context) -> None:
        super().__init__(context)
        self.api_url = "https://xiaoapi.cn/API/tq.php"
        self.timeout = aiohttp.ClientTimeout(total=10)
        self.headers = {"User-Agent": "AstrBot/WechatWeather"}

    def _parse_command_args(self, event) -> list:
        """多平台命令解析引擎"""
        try:
            # 微信平台处理逻辑
            if hasattr(event, 'content'):
                # 移除@机器人提及
                clean_content = re.sub(r"@[\w\s]+", "", event.content).strip()
                # 分割命令和参数
                parts = re.split(r"[\s\u3000]+", clean_content)  # 兼容全角空格
                return parts[1:] if len(parts) > 1 else []
            
            # 其他平台处理（QQ/Telegram等）
            return getattr(event, 'args', [])
        except Exception as e:
            logger.error(f"命令解析失败: {str(e)}")
            return []

    async def _fetch_weather(self, location: str) -> Optional[str]:
        """统一数据获取方法"""
        try:
            async with aiohttp.ClientSession(headers=self.headers, timeout=self.timeout) as session:
                async with session.get(self.api_url, params={"msg": location}) as resp:
                    if resp.status == 200:
                        return await resp.text(encoding='utf-8')
                    logger.error(f"API响应异常 HTTP {resp.status}")
        except Exception as e:
            logger.error(f"请求失败: {str(e)}")
        return None

    def _parse_weather(self, raw_data: str) -> dict:
        """增强数据解析器"""
        parsed = {"location": "未知地区"}
        
        # 基础信息解析
        if match := re.search(
            r"^[\w\s]+?(.*?)\s+"  # 匹配多级行政区划
            r"温度：([\d.-]+)℃\s+"
            r"体感：([\d.-]+)℃\s+"
            r"湿度：(\d+)%", 
            raw_data
        ):
            parsed.update({
                "location": match.group(1).split()[-1],  # 取最后一级地名
                "temp": match.group(2),
                "feel_temp": match.group(3),
                "humidity": match.group(4)
            })
        
        # 天气变化解析
        if change_match := re.search(
            r"您(.*?)正在下(.*?)哦，(.+?)，(.*)", 
            raw_data
        ):
            parsed.update({
                "rain": f"{change_match.group(1)}{change_match.group(2)}",
                "forecast": self._parse_forecast(change_match.group(4))
            })
        
        return parsed

    def _parse_forecast(self, forecast_str: str) -> list:
        """未来天气解析"""
        forecasts = []
        for part in forecast_str.split("转"):
            if "后" in part:
                time, weather = part.split("后", 1)
                forecasts.append(f"{time}后转{weather}")
            else:
                forecasts.append(part)
        return forecasts

    def _build_wechat_message(self, data: dict) -> str:
        """微信专用消息模板"""
        msg = [
            f"🌏【{data['location']}天气速报】",
            f"🌡️ 当前温度：{data['temp']}℃",
            f"🤒 体感温度：{data['feel_temp']}℃",
            f"💦 空气湿度：{data['humidity']}%"
        ]

        if 'rain' in data:
            msg.append(f"\n🌧️ 周边降水：\n您{data['rain']}中")

        if data.get('forecast'):
            msg.append("\n🕒 天气变化：")
            msg.extend([f"· {f}" for f in data['forecast']])

        msg.append("\n📡 数据来自中国气象局")
        return "\n".join(msg)

    @filter.command("天气", "查天气")
    async def get_weather(self, event: AstrMessageEvent):
        '''微信/QQ全平台天气查询'''
        try:
            # 多平台参数解析
            args = self._parse_command_args(event)
            location = "".join(args)
            
            if not location:
                yield CommandResult().error(
                    "📍 请提供查询地点\n"
                    "示例：\n"
                    "微信：@机器人 天气 北京朝阳\n"
                    "QQ：/天气 上海浦东"
                )
                return

            # 微信友好等待提示
            yield CommandResult().message(f"⛅ 正在获取【{location}】的天气...")

            if raw_data := await self._fetch_weather(location):
                weather_data = self._parse_weather(raw_data)
                yield CommandResult().message(self._build_wechat_message(weather_data))
            else:
                yield CommandResult().error(
                    "🌩️ 服务暂时不可用\n"
                    "可能原因：\n"
                    "1. 网络连接异常\n"
                    "2. 地址输入有误\n"
                    "请稍后重试"
                )

        except Exception as e:
            logger.error(f"处理异常: {str(e)}", exc_info=True)
            yield CommandResult().error("⚡ 系统开小差啦，请联系管理员")

    @filter.command("天气帮助")
    async def weather_help(self, event: AstrMessageEvent):
        """跨平台帮助信息"""
        help_msg = (
            "🌦️ 全平台使用指南 🌦️\n\n"
            "【微信】\n"
            "1. @机器人 天气 北京\n"
            "2. 直接发送'天气 上海'\n\n"
            "【QQ/其他】\n"
            "1. /天气 广州\n"
            "2. 查天气 成都\n\n"
            "🛠️ 故障反馈：\n"
            "请提供：\n"
            "1. 完整错误截图\n"
            "2. 查询时间\n"
            "3. 使用平台"
        )
        yield CommandResult().message(help_msg)

    @filter.command("网络诊断")
    async def network_check(self, event: AstrMessageEvent):
        """微信专用网络检测"""
        check_list = [
            ("气象数据中心", self.api_url),
            ("微信服务器", "https://weixin.qq.com"),
            ("公众平台", "https://mp.weixin.qq.com")
        ]
        
        results = []
        for name, url in check_list:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=8) as resp:
                        status = "✅ 正常" if resp.status == 200 else f"❌ 异常({resp.status})"
            except Exception as e:
                status = f"⚠️ 故障({str(e)[:15]})"
            results.append(f"{name}: {status}")
        
        report = (
            "📡 微信网络诊断报告\n\n"
            + "\n".join(results) +
            "\n\n🔧 自助修复建议：\n"
            "1. 切换WIFI/移动数据\n"
            "2. 重启微信客户端\n"
            "3. 等待5分钟重试"
        )
        yield CommandResult().message(report)
