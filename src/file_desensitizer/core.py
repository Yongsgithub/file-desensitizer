#!/usr/bin/env python3
"""
信息脱敏核心引擎
支持对姓名、手机号、身份证号码、住址、户籍地址、11位数字（学号等）、出生年月、邮箱、
银行卡号、邮政编码等敏感信息进行脱敏处理。

脱敏策略：
- 姓名：保留姓，名用*代替（如"张三"→"张*"，"张三丰"→"张**"）
- 手机号：保留前3后4，中间用****代替（如"13812345678"→"138****5678"）
- 身份证号：保留前6后4，中间用****代替（如"110101199001011234"→"110101********1234"）
- 住址：保留省市/区，详细地址用****代替
- 户籍地址：保留省市/区级，详细地址脱敏
- 11位数字：保留首3末3位，中间用*****代替（如"16126450238"→"161*****238"）
- 出生年月：保留年份，月份用**代替（如"2021年05月"→"2021年**月"）
- 邮箱：保留首字符和@后域名，中间用***代替
- 银行卡号：保留后4位，前面用****代替
- 邮政编码：保留首2位，末4位用****代替（如"518000"→"51****"）
"""

import re
import os
import sys
import json
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any


class TextDesensitizer:
    """文本内容脱敏器"""

    # ── 手机号 ──
    PHONE_PATTERN = re.compile(r'(?<!\d)(1[3-9]\d{1})\d{4}(\d{4})(?!\d)')
    PHONE_REPLACE = r'\1****\2'

    # ── 身份证号（18位和15位） ──
    ID_18_PATTERN = re.compile(
        r'(?<!\d)([1-9]\d{5})(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}([\dXx])(?!\d)'
    )
    ID_18_REPLACE = r'\1********\5'

    ID_15_PATTERN = re.compile(
        r'(?<!\d)([1-9]\d{5})\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}(?!\d)'
    )
    ID_15_REPLACE = r'\1********'

    # ── 邮箱 ──
    EMAIL_PATTERN = re.compile(r'([a-zA-Z0-9])[a-zA-Z0-9._%+-]*@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})')
    EMAIL_REPLACE = r'\1***@\2'

    # ── 银行卡号 ──
    BANKCARD_PATTERN = re.compile(r'(?<!\d)\d{12,19}(\d{4})(?!\d)')
    BANKCARD_REPLACE = r'****\1'

    # ── 通用11位纯数字 ── 学号/考生号等无标签的11位数字
    # 在手机号(1[3-9]开头)之后匹配，避免重复
    GENERAL_11DIGIT_PATTERN = re.compile(r'(?<!\d)(\d{3})\d{5}(\d{3})(?!\d)')
    GENERAL_11DIGIT_REPLACE = r'\1*****\2'

    # ── 邮政编码（6位数字）──
    POSTAL_CODE_LABEL = (
        r'(?:邮\s*政\s*编\s*码|邮\s*编|邮政编码|邮编|'
        r'post\s*code|zip\s*code|zip)'
    )
    # 带标签: 邮编：518000
    POSTAL_CODE_LABELED_PATTERN = re.compile(
        rf'{POSTAL_CODE_LABEL}'
        r'[：:\s=]*'
        r'(?P<code>\d{6})'
        r'(?!\d)'
    )
    # 无标签纯6位数字（保守匹配，排除已脱敏文本中的数字片段）
    POSTAL_CODE_STANDALONE = re.compile(
        r'(?<!\d)(?<!\*)(\d{2})\d{4}(?![\d\*])'
    )
    POSTAL_CODE_STANDALONE_REPLACE = r'\1****'

    # ── 出生年月 ── 匹配 "出生年月：2021年05月" 等格式，含 YYYY.MM.DD
    BIRTH_DATE_PATTERN = re.compile(
        r'(出\s*生\s*年\s*月|出\s*生\s*日\s*期|出\s*生\s*时\s*间)'
        r'[：:\s=]*'
        r'((?:19|20)\d{2})'
        r'[\s年.\-/\u4e00-\u9fff]*'
        r'(\d{1,2})'
        r'[\s月.\-/\u4e00-\u9fff]*'
        r'(\d{1,2})?'  # 可选日
    )

    # ── 户籍地址（带标签的高置信度地址）──
    HOUSEHOLD_LABEL = (
        r'(?:户\s*籍\s*地\s*址|户\s*籍\s*所\s*在\s*地|户\s*籍\s*所\s*在|'
        r'户\s*口\s*所\s*在\s*地|户\s*籍\s*地)'
    )
    HOUSEHOLD_ADDRESS_PATTERN = re.compile(
        rf'{HOUSEHOLD_LABEL}'
        r'[：:\s=]*'
        rf'([\u4e00-\u9fff\w\d\s\-\#\(\)（）、，,]{{4,200}})'
    )

    # ── 住址相关模式 ──
    # 中国省份/直辖市/自治区
    PROVINCES = (
        r'(?:北京|上海|天津|重庆|河北|山西|辽宁|吉林|黑龙江|江苏|浙江|安徽|福建|江西|山东|河南|'
        r'湖北|湖南|广东|海南|四川|贵州|云南|陕西|甘肃|青海|台湾|内蒙古|广西|西藏|宁夏|新疆|'
        r'香港|澳门|北京市|上海市|天津市|重庆市|河北省|山西省|辽宁省|吉林省|黑龙江省|江苏省|'
        r'浙江省|安徽省|福建省|江西省|山东省|河南省|湖北省|湖南省|广东省|海南省|四川省|贵州省|'
        r'云南省|陕西省|甘肃省|青海省|台湾省|内蒙古自治区|广西壮族自治区|西藏自治区|'
        r'宁夏回族自治区|新疆维吾尔自治区|香港特别行政区|澳门特别行政区)'
    )

    # 地址：省/市/区/县/镇/路/街/号/栋/单元/室 等组合
    ADDRESS_KEYWORDS = (
        r'(?:市|区|县|镇|乡|村|街道|路|街|巷|弄|号|栋|幢|单元|室|层|楼|'
        r'小区|花园|苑|公寓|大厦|广场|中心|开发区|高新区|新区|片区|组|队)'
    )

    # 完整地址匹配模式（省级开头 + 地址关键词结尾，中间至少10个字符）
    ADDRESS_FULL_PATTERN = re.compile(
        rf'({PROVINCES})\s*[\u4e00-\u9fff\w]{{8,80}}?(?:{ADDRESS_KEYWORDS})[\u4e00-\u9fff\w]{{0,30}}'
    )

    # 更通用的地址模式（包含地址关键词的较长文本）
    ADDRESS_GENERAL_PATTERN = re.compile(
        rf'(?:[\u4e00-\u9fff]{{2,6}}(?:省|市|自治区|特别行政区))?'
        rf'[\u4e00-\u9fff]{{2,6}}(?:市|区|县|自治州|盟|旗)'
        rf'[\u4e00-\u9fff\w\d]{{3,60}}?'
        rf'(?:{ADDRESS_KEYWORDS})'
        rf'[\u4e00-\u9fff\d\-\#]{{0,20}}'
    )

    # 短地址模式（如 XX路XX号、XX街XX号）
    ADDRESS_SHORT_PATTERN = re.compile(
        rf'[\u4e00-\u9fff]{{2,20}}(?:路|街|巷|弄|大道|大街)'
        rf'[\u4e00-\u9fff\d\-\#]{{1,20}}(?:号|栋|幢|单元|室|层|楼)'
    )

    @classmethod
    def desensitize_text(cls, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        对文本进行脱敏处理。

        Args:
            text: 原始文本

        Returns:
            (脱敏后文本, 脱敏记录列表)
        """
        records = []
        result = text

        # 记录原始文本片段，用于生成脱敏记录
        def make_record(category, original, masked):
            records.append({
                "category": category,
                "original": original,
                "masked": masked
            })

        # 1. 身份证号（先处理，避免被其他模式干扰）
        for match in cls.ID_18_PATTERN.finditer(result):
            make_record("身份证号", match.group(), cls.ID_18_PATTERN.sub(cls.ID_18_REPLACE, match.group()))

        for match in cls.ID_15_PATTERN.finditer(result):
            make_record("身份证号(15位)", match.group(), cls.ID_15_PATTERN.sub(cls.ID_15_REPLACE, match.group()))

        result = cls.ID_18_PATTERN.sub(cls.ID_18_REPLACE, result)
        result = cls.ID_15_PATTERN.sub(cls.ID_15_REPLACE, result)

        # 1.5 出生年月（身份证脱敏后处理，避免身份证中日期被误匹配）
        result = cls._desensitize_birth_date(result, records, make_record)

        # 2. 手机号（1[3-9]开头的11位数字）
        for match in cls.PHONE_PATTERN.finditer(result):
            full = match.group()
            masked = cls.PHONE_PATTERN.sub(cls.PHONE_REPLACE, full)
            records.append({
                "category": "手机号",
                "original": full,
                "masked": masked,
                "search_text": full,  # 纯数字，PDF 中直接定位
            })
        result = cls.PHONE_PATTERN.sub(cls.PHONE_REPLACE, result)

        # 2.5 通用11位数字（非手机号的11位纯数字，如学号16126450238）
        result = cls._desensitize_11digit(result, records)

        # 3. 邮政编码（带标签优先，再处理独立6位数字）
        result = cls._desensitize_postal_code(result, records)

        # 4. 银行卡号 (12-19位)
        for match in cls.BANKCARD_PATTERN.finditer(result):
            full = match.group()
            masked = cls.BANKCARD_PATTERN.sub(cls.BANKCARD_REPLACE, full)
            records.append({
                "category": "银行卡号",
                "original": full,
                "masked": masked,
                "search_text": full,
            })
        result = cls.BANKCARD_PATTERN.sub(cls.BANKCARD_REPLACE, result)

        # 5. 邮箱
        for match in cls.EMAIL_PATTERN.finditer(result):
            make_record("邮箱", match.group(), cls.EMAIL_PATTERN.sub(cls.EMAIL_REPLACE, match.group()))
        result = cls.EMAIL_PATTERN.sub(cls.EMAIL_REPLACE, result)

        # 6. 住址 / 户籍地址（使用已处理集合避免重复脱敏）
        processed_positions = set()

        def safe_replace(text, start, end, replacement):
            """安全替换，记录已处理位置避免重复"""
            pos_key = (start, end)
            if pos_key in processed_positions:
                return text, False
            # 检查是否与已处理位置重叠
            for ps, pe in processed_positions:
                if not (end <= ps or start >= pe):
                    return text, False
            processed_positions.add(pos_key)
            return text[:start] + replacement + text[end:], True

        # 6a. 户籍地址（带标签，高置信度，优先处理）
        for match in cls.HOUSEHOLD_ADDRESS_PATTERN.finditer(result):
            address_content = match.group(1).strip()
            if len(address_content) >= 2:
                masked_content = cls._mask_address(address_content)
                full_original = match.group()
                # 使用 match 的精确位置信息构造替换文本
                content_start_in_full = match.start(1) - match.start()
                prefix = full_original[:content_start_in_full]
                masked_full = prefix + masked_content
                new_result, replaced = safe_replace(result, match.start(), match.end(), masked_full)
                if replaced:
                    result = new_result
                    # search_text 用地址内容（不含标签），便于 PDF 中定位
                    records.append({
                        "category": "户籍地址",
                        "original": full_original,
                        "masked": masked_full,
                        "search_text": address_content,
                    })

        # 6b. 通用地址匹配：合并所有地址模式，按长度降序排列（长匹配优先）
        all_address_matches = []

        for pattern in [cls.ADDRESS_FULL_PATTERN, cls.ADDRESS_GENERAL_PATTERN, cls.ADDRESS_SHORT_PATTERN]:
            for match in pattern.finditer(result):
                all_address_matches.append((match.start(), match.end(), match.group()))

        # 按匹配长度降序排列，长地址优先处理
        all_address_matches.sort(key=lambda x: -(x[1] - x[0]))

        for start, end, original in all_address_matches:
            masked = cls._mask_address(original)
            new_result, replaced = safe_replace(result, start, end, masked)
            if replaced:
                result = new_result
                make_record("住址", original, masked)

        # 7. 姓名（使用常见姓氏表 + 上下文推断）
        result = cls._desensitize_names(result, records)

        return result, records

    @classmethod
    def _mask_address(cls, address: str) -> str:
        """对地址进行脱敏：保留省市/区级信息，后续用****代替"""
        # 尝试找到区/县/市级别的边界
        district_match = re.search(
            r'([\u4e00-\u9fff]{2,6}(?:省|市|自治区|特别行政区))?'
            r'([\u4e00-\u9fff]{2,6}(?:市|区|县|自治州|盟|旗))',
            address
        )
        if district_match:
            end_pos = district_match.end()
            prefix = address[:end_pos]
            # 后续部分保留首尾字符
            suffix = address[end_pos:]
            if len(suffix) > 8:
                masked_suffix = suffix[:2] + '****' + suffix[-2:]
            elif len(suffix) > 3:
                masked_suffix = suffix[0] + '****'
            else:
                masked_suffix = '****'
            return prefix + masked_suffix

        # 无法定位区/县级，简单处理
        if len(address) > 8:
            return address[:4] + '****' + address[-2:]
        elif len(address) > 4:
            return address[:2] + '****'
        return '****'

    @classmethod
    def _desensitize_birth_date(cls, text: str, records: List[Dict],
                                 make_record) -> str:
        """对出生年月进行脱敏：保留年份，月份用**代替"""
        def birth_replacer(match):
            label = match.group(1)       # "出生年月" 等
            year = match.group(2)        # "2021"
            month = match.group(3)       # "05"
            day = match.group(4)         # 可选 "09"
            full = match.group()
            # 替换月份为 **
            masked = full.replace(month, '**', 1)
            # search_text 取完整日期值（不含标签），便于 PDF 中定位
            search_text = year
            # 从 full 中提取标签后的日期部分
            label_end = full.find(year)
            if label_end > 0:
                search_text = full[label_end:]
            records.append({
                "category": "出生年月",
                "original": full,
                "masked": masked,
                "search_text": search_text,
            })
            return masked

        return cls.BIRTH_DATE_PATTERN.sub(birth_replacer, text)

    @classmethod
    def _desensitize_11digit(cls, text: str, records: List[Dict]) -> str:
        """匹配并脱敏任意11位纯数字（非手机号，手机号已在前步处理）。
        保留首3位和末3位，中间5位用*****代替。
        search_text 为完整11位数字，便于 PDF 中精确定位。
        """
        def replacer(match):
            full = match.group()
            masked = match.group(1) + '*****' + match.group(2)
            records.append({
                "category": "11位数字(学号等)",
                "original": full,
                "masked": masked,
                "search_text": full,
            })
            return masked
        return cls.GENERAL_11DIGIT_PATTERN.sub(replacer, text)

    @classmethod
    def _desensitize_postal_code(cls, text: str, records: List[Dict]) -> str:
        """匹配并脱敏邮政编码（6位数字）。
        优先匹配带标签的（如 '邮编 518000'），再处理独立的6位数字。
        保留首2位，末4位用****代替。
        search_text 为完整6位数字，便于 PDF 中精确定位。
        """
        result = text

        # 第一遍：带标签的邮政编码（高置信度）
        def labeled_replacer(match):
            full = match.group()
            code = match.group('code')
            masked_code = code[:2] + '****'
            masked = full.replace(code, masked_code, 1)
            records.append({
                "category": "邮政编码",
                "original": full,
                "masked": masked,
                "search_text": code,
            })
            return masked
        result = cls.POSTAL_CODE_LABELED_PATTERN.sub(labeled_replacer, result)

        # 第二遍：独立的6位数字（已处理过的邮政编码不会再匹配）
        def standalone_replacer(match):
            full = match.group()
            masked = match.group(1) + '****'
            records.append({
                "category": "邮政编码",
                "original": full,
                "masked": masked,
                "search_text": full,
            })
            return masked
        result = cls.POSTAL_CODE_STANDALONE.sub(standalone_replacer, result)

        return result

    @classmethod
    def _desensitize_names(cls, text: str, records: List[Dict]) -> str:
        """对中文姓名进行脱敏"""
        # 常见中国姓氏
        common_surnames = set(
            '王李张刘陈杨黄赵周吴徐孙马胡朱郭何罗高林郑梁谢唐许冯宋韩邓彭曹曾田萧潘袁蔡蒋余于杜叶程魏苏吕丁'
            '任卢姚沈钟姜崔谭陆范汪廖石金贾夏韦付方白邹孟熊秦邱江尹薛闫段雷侯龙史陶黎贺顾毛郝龚邵万钱严覃'
            '武戴莫孔向汤温康施文牛樊葛邢安齐易乔伍庞颜倪庄聂章鲁岳翟殷詹申欧耿关兰焦俞左柳甘祝包宁尚'
            '梅阮黎尤舒柯屠褚翁霍游阮冉祁牟植郁郎滕娄桑谌柏隋鄢辜吉饶刁瞿戚丘古米池滕艾蓝'
        )

        # 匹配模式：常见姓氏 + 1~3个汉字（含复姓前缀可能）
        # 注意：边界排除 * 号，防止已脱敏的"杨睿*"中的"杨睿"被再次匹配
        name_pattern = re.compile(
            r'(?<![a-zA-Z0-9\u4e00-\u9fff\*])'
            r'([\u4e00-\u9fff]{1,2})'  # 姓氏（含复姓第一字）
            r'([\u4e00-\u9fff]{1,3})'   # 名字
            r'(?![a-zA-Z0-9\u4e00-\u9fff\*])'
        )

        # 已处理的姓名集合，避免子串重复匹配
        processed_names = set()

        def name_replacer(match):
            surname = match.group(1)
            given = match.group(2)
            full_word = match.group()

            # 检查是否为常见姓氏
            if surname[0] not in common_surnames and surname not in common_surnames:
                return full_word

            # 排除明显不是名字的情况（如包含数字、英文等）
            if re.search(r'[\dA-Za-z]', full_word):
                return full_word

            # 排除一些常见非名字词组
            exclude_words = {
                '我们', '他们', '你们', '这个', '那个', '什么', '怎么', '可以', '不是',
                '已经', '因为', '所以', '如果', '虽然', '但是', '而且', '或者', '并且',
                '一定', '可能', '应该', '需要', '能够', '必须', '所有', '任何', '其他',
                '对于', '关于', '根据', '通过', '经过', '按照', '为了', '除了', '包括',
                '部分', '地方', '方面', '方式', '方法', '过程', '结果', '情况', '条件',
                '公司', '集团', '有限', '责任', '股份', '企业', '管理', '服务', '技术',
                '系统', '平台', '中心', '部门', '项目', '产品', '市场', '客户', '数据',
                '政策', '法律', '规定', '标准', '要求', '报告', '分析', '研究', '开发',
                '问题', '回答', '说明', '介绍', '通知', '公告', '声明', '协议', '合同',
                '电脑', '手机', '网络', '软件', '硬件', '设备', '设施', '材料', '资源',
                '什么', '怎么', '为什么', '哪里', '哪位', '如何', '怎么样',
                '姓名', '性别', '年龄', '出生', '民族', '籍贯', '学历', '职业',
                '政治', '经济', '文化', '社会', '教育', '科学', '卫生', '体育',
                '关系', '身份', '联系', '方式', '地址', '电话', '号码', '日期', '时间',
                '配偶', '子女', '父母', '兄弟', '姐妹', '朋友', '同学', '同事', '领导',
                '备注', '附件', '文件', '编号', '序号', '金额', '数量', '单价', '总计',
                '申请', '左右', '前后', '上下', '多少', '大小', '高低', '长短', '轻重',
                '签名', '意见', '审批', '批准', '审核', '复核', '核准', '同意', '否决',
                '经办', '主办', '协办', '承办', '督办', '交办', '转办', '阅办',
                '本人', '单位', '组织', '机构', '机关', '团体', '协会', '学会',
                '学号', '班级', '专业', '院系', '年级', '课程', '成绩', '学分',
                '家庭', '成员', '主要', '基本', '以上', '以下', '以内', '以外',
                '申请', '申请人', '签名', '填写', '提交', '打印', '复印', '扫描',
                '助学金', '奖学金', '申请表', '审批表', '登记表', '汇总表',
                '于前茅', '严于律己', '名列前茅', '兢兢业业', '勤勤恳恳', '踏踏实实',
                '刻苦努力', '努力学', '认真学', '积极向', '努力工', '认真工',
                '遵守', '严格', '积极', '参加', '获得', '取得', '评为', '荣获',
            }
            if full_word in exclude_words:
                return full_word

            # 额外排除：如果匹配的整个文本片段出现在排除词中
            for ew in exclude_words:
                if ew in full_word and len(full_word) >= len(ew):
                    # 检查是否是排除词作为前缀的复合词（如"申请人签名"包含"申请人"）
                    if full_word.startswith(ew) or full_word.endswith(ew):
                        return full_word

            # 避免子串重复：如果当前匹配是已处理姓名的子串或包含关系，跳过
            for pn in processed_names:
                if full_word in pn or pn in full_word:
                    return full_word

            # 脱敏：保留姓，名用*代替
            masked_name = surname + '*' * len(given)
            processed_names.add(full_word)
            records.append({
                "category": "姓名",
                "original": full_word,
                "masked": masked_name
            })
            return masked_name

        return name_pattern.sub(name_replacer, text)

    @classmethod
    def desensitize_file_path(cls, file_path: str) -> str:
        """
        对文件名中的敏感信息进行脱敏。

        Args:
            file_path: 原始文件路径

        Returns:
            脱敏后的文件路径
        """
        path = Path(file_path)
        stem = path.stem
        suffix = path.suffix

        desensitized_stem, _ = cls.desensitize_text(stem)
        # 移除文件名中的不安全字符
        desensitized_stem = re.sub(r'[<>:"/\\|?*]', '_', desensitized_stem)
        desensitized_stem = desensitized_stem.strip().strip('.')

        if not desensitized_stem:
            desensitized_stem = 'desensitized'

        new_name = desensitized_stem + suffix
        return str(path.parent / new_name)


def desensitize_text(text: str) -> Tuple[str, List[Dict[str, Any]]]:
    """便捷函数：对文本进行脱敏"""
    return TextDesensitizer.desensitize_text(text)


def desensitize_file_path(file_path: str) -> str:
    """便捷函数：对文件路径进行脱敏"""
    return TextDesensitizer.desensitize_file_path(file_path)


if __name__ == "__main__":
    # 简单测试
    test_texts = [
        "张三，手机号13812345678，身份证110101199001011234，住在北京市朝阳区建国路88号12栋3单元501室",
        "李四丰的邮箱是lisi@example.com，银行卡号6222021234567890123",
        "王五，联系电话：13987654321，住址：上海市浦东新区陆家嘴环路1000号恒生银行大厦",
        "赵六，身份证号：440305198506150078，电话15600001111",
        # 学号+出生年月+户籍地址
        "学号：20240100123，出生年月：2021年05月，户籍地址：广东省深圳市南山区科技园路88号",
        "学籍号：G44030520050615，出生日期：2005年06月15日，户籍所在地：北京市海淀区中关村大街1号",
        "考生号：24440101110001，出生时间：1998年12月，户口所在地：浙江省杭州市西湖区浙大路38号",
        # 新增：纯11位数字 + 邮政编码
        "学（籍）号 16126450238，邮政编码 518000，邮编：100081",
        "学校中山职业技术学院 学（籍）号 16126450238 年级 23级 班别 23大数据班",
        "出生年月 2004.10.09，身份证号 522401200513097020，户籍地址 海南省毕节市七星关区粤海街道大沙地村3组58号",
    ]
    for t in test_texts:
        result, records = desensitize_text(t)
        print(f"原文: {t}")
        print(f"脱敏: {result}")
        for r in records:
            s = r.get('search_text', '')
            print(f"  [{r['category']}] {r['original'][:50]} → {r['masked'][:50]}  | search={s[:30]}")
        print()
