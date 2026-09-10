#!/usr/bin/env python3
"""音色生成 — 为角色生成参考音频

用法：
  vcshort gen-voice <项目路径> --name <角色名> --gender <male|female>
  vcshort gen-voice <项目路径> --name <角色名> --gender male --force  # 不满意重新生成，换一个音色

流程：
  1. 根据性别从音色池随机选一个 TTS 音色
  2. 调用火山引擎豆包语音合成 API 生成一段参考音频
  3. 保存到 assets/characters/<角色名>/<角色名>.wav
  4. 记录使用的音色到 assets/characters/<角色名>/voice.json，重新生成时换一个
"""

import argparse
import base64
import json
import random
import sys
import requests
import yaml
from pathlib import Path

TTS_ENDPOINT = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"

# 豆包语音合成 2.0 音色池（seed-tts-2.0）
MALE_VOICES = [
    ("zh_male_m191_uranus_bigtts", "云舟"),
    ("zh_male_taocheng_uranus_bigtts", "小天"),
    ("zh_male_ruyayichen_uranus_bigtts", "儒雅逸辰"),
    ("zh_male_dayi_uranus_bigtts", "大壹"),
    ("zh_male_jieshuoxiaoming_uranus_bigtts", "解说小明"),
    ("zh_male_yizhipiannan_uranus_bigtts", "译制片男"),
    ("zh_male_linjiananhai_uranus_bigtts", "邻家男孩"),
    ("zh_male_silang_uranus_bigtts", "四郎"),
    ("zh_male_ruyaqingnian_uranus_bigtts", "儒雅青年"),
    ("zh_male_qingcang_uranus_bigtts", "擎苍"),
    ("zh_male_shaonianzixin_uranus_bigtts", "少年自信"),
    ("zh_male_liufei_uranus_bigtts", "刘飞"),
]

FEMALE_VOICES = [
    ("zh_female_xiaohe_uranus_bigtts", "小何"),
    ("zh_female_vv_uranus_bigtts", "Vivi"),
    ("zh_female_qingxinnvsheng_uranus_bigtts", "清新女声"),
    ("zh_female_cancan_uranus_bigtts", "知性灿灿"),
    ("zh_female_sajiaoxuemei_uranus_bigtts", "撒娇学妹"),
    ("zh_female_tianmeixiaoyuan_uranus_bigtts", "甜美小源"),
    ("zh_female_tianmeitaozi_uranus_bigtts", "甜美桃子"),
    ("zh_female_shuangkuaisisi_uranus_bigtts", "爽快思思"),
    ("zh_female_linjianvhai_uranus_bigtts", "邻家女孩"),
    ("zh_female_meilinvyou_uranus_bigtts", "魅力女友"),
    ("zh_female_liuchangnv_uranus_bigtts", "流畅女声"),
]

# 参考台词模板，生成 5-10 秒音频
SAMPLE_TEXTS = [
    "你好，我是{name}。我一直在想，这个世界到底怎么了。",
    "我叫{name}。不管发生什么，我都会活下去。",
    "你好，我是{name}。这片废墟里，还有我们需要守护的东西。",
]


def load_config(project_root: Path) -> dict:
    config_path = project_root / "config.yaml"
    if not config_path.exists():
        print("错误：config.yaml 不存在", file=sys.stderr)
        sys.exit(1)
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def pick_voice(gender: str, used_voices: list) -> tuple:
    """根据性别选一个未用过的音色，用完了就重新循环。"""
    pool = MALE_VOICES if gender == "male" else FEMALE_VOICES
    available = [v for v in pool if v[0] not in used_voices]
    if not available:
        available = pool  # 全都用过了，重新来
    return random.choice(available)


def generate_voice(text: str, speaker: str, tts_config: dict,
                   instruction: str = None, emotion: str = None, emotion_scale: int = None) -> bytes:
    """调用火山引擎 TTS API，返回音频二进制数据。

    instruction: 自然语言情感指令，写入 additions.context_texts（如 "用凶狠霸道的语气说"）
    emotion: 情感标签，写入 audio_params.emotion（如 "angry"）
    emotion_scale: 情感强度 1-5，写入 audio_params.emotion_scale
    """
    api_key = tts_config.get("api_key")
    app_id = tts_config.get("app_id")
    access_key = tts_config.get("access_key")
    resource_id = tts_config.get("resource_id", "seed-tts-2.0")

    headers = {
        "Content-Type": "application/json",
        "X-Api-Resource-Id": resource_id,
    }
    if api_key:
        headers["X-Api-Key"] = api_key
    elif app_id and access_key:
        headers["X-Api-App-Id"] = app_id
        headers["X-Api-Access-Key"] = access_key
    else:
        print("错误：config.yaml 中未配置 tts.api_key 或 tts.app_id + tts.access_key", file=sys.stderr)
        sys.exit(1)

    audio_params = {
        "format": "mp3",
        "sample_rate": 24000,
    }
    if emotion:
        audio_params["emotion"] = emotion
    if emotion_scale is not None:
        audio_params["emotion_scale"] = emotion_scale

    req_params = {
        "text": text,
        "speaker": speaker,
        "audio_params": audio_params,
    }
    # additions 里的 context_texts 支持自然语言情感指令
    # seed-tts-2.0-expressive 模型能增强 2.0 音色的情感表现力
    additions = {}
    if instruction:
        additions["context_texts"] = [instruction]
    additions["model"] = "seed-tts-2.0-expressive"
    req_params["additions"] = json.dumps(additions, ensure_ascii=False)

    payload = {
        "user": {"uid": "vcshort"},
        "req_params": req_params,
    }

    resp = requests.post(TTS_ENDPOINT, json=payload, headers=headers, timeout=60)
    if resp.status_code != 200:
        print(f"TTS API 错误 ({resp.status_code}): {resp.text}", file=sys.stderr)
        sys.exit(1)

    # V3 HTTP 响应体可能是音频二进制，也可能是 JSON / NDJSON + base64 data
    content_type = resp.headers.get("Content-Type", "")
    if "audio" in content_type or resp.content[:4] == b"\xff\xfb" or resp.content[:4] == b"ID3":
        return resp.content

    # 尝试解析 JSON / NDJSON（多行 JSON，每行带一段 base64 音频）
    try:
        audio_b64_parts = []
        has_error = False
        for line in resp.text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            part = json.loads(line)
            code = part.get("code", -1)
            # 火山 TTS 成功码：0 为音频数据段，20000000 为最终 OK 标记
            if code == 0 or code == 20000000:
                if isinstance(part.get("data"), str) and part["data"]:
                    audio_b64_parts.append(part["data"])
                continue
            has_error = True
            print(f"TTS API 返回异常: {part}", file=sys.stderr)

        if not has_error and audio_b64_parts:
            return base64.b64decode("".join(audio_b64_parts))

        if has_error:
            sys.exit(1)
        # 没有任何 data 段
        print(f"TTS API 返回异常: {resp.text[:500]}", file=sys.stderr)
    except Exception:
        print(f"TTS API 返回异常: {resp.text[:500]}", file=sys.stderr)
    sys.exit(1)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="vcshort gen-voice", description="为角色生成音色参考音频")
    parser.add_argument("project", help="项目路径")
    parser.add_argument("--name", required=True, help="角色名（对应 assets/characters/<角色名>/）")
    parser.add_argument("--gender", required=True, choices=["male", "female"], help="角色性别")
    parser.add_argument("--voice", help="指定音色 ID（如 zh_male_qingcang_uranus_bigtts），不指定则随机选")
    parser.add_argument("--instruction", help="自然语言情感指令，控制语气语调（如 \"用凶狠霸道的语气说\"）")
    parser.add_argument("--emotion", help="情感标签（如 angry/happy/sad），写入 audio_params.emotion")
    parser.add_argument("--emotion-scale", type=int, choices=range(1, 6), help="情感强度 1-5，需配合 --emotion 使用")
    parser.add_argument("--force", action="store_true", help="覆盖已有音色，换一个新音色")
    args = parser.parse_args(argv)

    project_root = Path(args.project).resolve()
    if not project_root.exists():
        print(f"错误：项目路径不存在: {project_root}", file=sys.stderr)
        return 1

    char_dir = project_root / "assets" / "characters" / args.name
    if not char_dir.is_dir():
        print(f"错误：角色目录不存在: {char_dir}", file=sys.stderr)
        print("请先用 gen-image 生成角色图片", file=sys.stderr)
        return 1

    # 读取 character.yaml 档案（voice 段）
    char_yaml_path = char_dir / "character.yaml"
    char_yaml = {}
    if char_yaml_path.exists():
        with open(char_yaml_path, encoding="utf-8") as f:
            char_yaml = yaml.safe_load(f) or {}
    voice_cfg = char_yaml.get("voice") or {}

    voice_path = char_dir / f"{args.name}.mp3"
    meta_path = char_dir / "voice.json"

    # 检查已有音色
    if voice_path.exists() and not args.force:
        print(f"音色文件已存在: {voice_path}")
        print("使用 --force 重新生成（会换一个新音色）")
        return 0

    # 读取已用过的音色列表
    used_voices = []
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            used_voices = meta.get("used_voices", [])
        except Exception:
            pass

    # 选音色：CLI --voice > character.yaml voice.speaker > 随机
    speaker_override = args.voice or voice_cfg.get("speaker") or ""
    if speaker_override:
        pool = MALE_VOICES if args.gender == "male" else FEMALE_VOICES
        speaker_id = speaker_override
        speaker_name = next((n for sid, n in pool if sid == speaker_id), speaker_id)
    else:
        speaker_id, speaker_name = pick_voice(args.gender, used_voices)
    print(f"角色: {args.name}（{args.gender}）")
    print(f"音色: {speaker_name}（{speaker_id}）")

    # 生成台词
    text = random.choice(SAMPLE_TEXTS).format(name=args.name)
    print(f"台词: {text}")

    # 读取 TTS 配置
    config = load_config(project_root)
    tts_config = config.get("tts") or {}
    if not tts_config:
        print("错误：config.yaml 中未配置 tts 段（需要 api_key 或 app_id + access_key）", file=sys.stderr)
        return 1

    # 情感控制：CLI 参数 > character.yaml voice 段
    instruction = args.instruction or voice_cfg.get("instruction") or ""
    emotion = args.emotion or voice_cfg.get("emotion") or ""
    emotion_scale = args.emotion_scale or voice_cfg.get("emotion_scale")

    # 调用 TTS API
    print("正在生成音色...")
    if instruction:
        print(f"情感指令: {instruction}")
    if emotion:
        print(f"情感: {emotion}" + (f"（强度 {emotion_scale}）" if emotion_scale else ""))
    audio_data = generate_voice(text, speaker_id, tts_config,
                                instruction=instruction or None,
                                emotion=emotion or None,
                                emotion_scale=emotion_scale)

    # 保存音频
    voice_path.write_bytes(audio_data)
    print(f"已保存: {voice_path}")

    # 保存元数据
    used_voices.append(speaker_id)
    meta = {
        "speaker_id": speaker_id,
        "speaker_name": speaker_name,
        "gender": args.gender,
        "used_voices": used_voices,
    }
    if instruction:
        meta["instruction"] = instruction
    if emotion:
        meta["emotion"] = emotion
        if emotion_scale:
            meta["emotion_scale"] = emotion_scale
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n✅ 音色生成完成")
    print(f"   角色: {args.name}")
    print(f"   音色: {speaker_name}（{speaker_id}）")
    print(f"   文件: {voice_path}")
    print(f"   不满意？运行: vcshort gen-voice {project_root} --name {args.name} --gender {args.gender} --force")
    return 0
