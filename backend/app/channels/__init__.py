"""Channel capabilities are explicit; unsupported platforms never fake receipts."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ChannelCapability:
    key: str
    label: str
    can_submit: bool
    per_job_attachment: bool
    receipt_kind: str
    explanation: str


CHANNELS = {
    "prepare_open": ChannelCapability(
        "prepare_open", "准备材料并打开原入口", False, False, "prepared",
        "材料准备完成后由用户在原始招聘入口提交。",
    ),
    "boss": ChannelCapability(
        "boss", "BOSS 直聘", False, False, "prepared",
        "当前未接入获准提交 API，仅准备定制简历和开场白。",
    ),
    "wechat": ChannelCapability(
        "wechat", "微信 / 小程序", False, False, "prepared",
        "公众号文章可导入；任意小程序没有通用投递接口。",
    ),
    "linkedin": ChannelCapability(
        "linkedin", "LinkedIn", False, False, "prepared",
        "保存原申请入口；当前连接器不执行外部提交。",
    ),
    "email": ChannelCapability(
        "email", "招聘邮件 SMTP", True, True, "mail_accepted",
        "需服务器开启发送、招聘地址允许名单和策略授权；邮件受理不代表申请受理。",
    ),
}


def channel_list() -> list[dict]:
    return [asdict(value) for value in CHANNELS.values()]
