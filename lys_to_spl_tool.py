import os
import re
from github import Github
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def convert_ms(ms, offset=0):
    """精确处理时间偏移和负数"""
    adjusted = int(ms) + offset
    adjusted = max(adjusted, 0)  # 防止负时间
    minutes, ms = divmod(adjusted, 60000)
    seconds, milliseconds = divmod(ms, 1000)
    return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

def parse_issue_content(content):
    """增强型Issue内容解析"""
    try:
        # 使用更健壮的正则表达式
        offset_match = re.search(r'### offset\s+([\d-]+)', content, re.IGNORECASE)
        lys_match = re.search(r'### LYS 歌词\s+((?:\[.*?\]\s*.*?\n?)+)', content, re.IGNORECASE|re.DOTALL)
        
        offset = int(offset_match.group(1).strip()) if offset_match else 0
        lys_content = lys_match.group(1).strip() if lys_match else ''
        return offset, lys_content
    except Exception as e:
        logger.error(f"内容解析失败: {str(e)}")
        return 0, ''

def lys_to_spl(lys_text, time_offset=0):
    """最终整合版转换核心"""
    spl_lines = []
    word_pattern = re.compile(r'''
        (.*?)                # 非贪婪匹配所有字符
        \s*                  # 吸收空白
        \((\d+),(\d+)\)      # 时间参数
    ''', re.VERBOSE|re.DOTALL)
    
    for line in lys_text.split('\n'):
        line = line.strip()
        if not line.startswith('['):
            continue

        # 分离行属性
        prop_match = re.match(r'\[(\d+)\](.*)', line)
        if not prop_match:
            continue
            
        content = prop_match.group(2)
        word_entries = word_pattern.findall(content)
        
        if not word_entries:
            continue

        segments = []
        last_end = 0
        for idx, (word, s, d) in enumerate(word_entries):
            original_start = int()
            start = original_start + time_offset
            duration = int(d)
            end = original_start + duration + time_offset
            
            # 完整保留原始格式（含空格和括号）
            cleaned_word = word.replace('\n', ' ').replace('\r', '').rstrip()
            if word.endswith(' '):  # 保留结尾空格
                cleaned_word += ' '
                
            # 生成时间戳
            segments.append(f"[{convert_ms(start)}]{cleaned_word}")
            
            # 处理间隔
            if idx < len(word_entries)-1:
                next_start = int(word_entries[idx+1][1]) + time_offset
                if end < next_start:
                    segments.append(f"[{convert_ms(end)}]")
            
            last_end = end
        
        if segments:
            segments.append(f"[{convert_ms(last_end)}]")
            spl_lines.append(''.join(segments))
    
    return '\n'.join(spl_lines)

def main():
    """GitHub集成主函数"""
    token = os.getenv('GITHUB_TOKEN')
    issue_number = int(os.getenv('ISSUE_NUMBER'))
    repo_name = os.getenv('GITHUB_REPOSITORY')

    if not all([token, issue_number, repo_name]):
        logger.error("缺少必要的环境变量")
        return

    try:
        # 初始化GitHub连接
        g = Github(token)
        repo = g.get_repo(repo_name)
        issue = repo.get_issue(number=issue_number)
        
        # 解析内容
        offset, lys_content = parse_issue_content(issue.body)
        logger.info(f"解析成功 | Offset: {offset} | 歌词行数: {len(lys_content.splitlines())}")
        
        if not lys_content:
            issue.create_comment("错误：未检测到有效的LYS歌词内容")
            return

        # 执行转换
        try:
            spl_output = lys_to_spl(lys_content, offset)
            logger.debug(f"转换结果示例:\n{spl_output[:500]}")  # 日志记录前500字符
            comment = f"**输出:**\n```\n{spl_output}\n```"
        except Exception as e:
            logger.exception("转换过程异常")
            comment = f"错误：歌词转换失败 - {str(e)}"

        # 提交结果
        issue.create_comment(comment)
        logger.info("处理结果已成功提交")

    except Exception as e:
        logger.exception("GitHub操作失败")
        try:
            issue.create_comment(f"系统错误：{str(e)}")
        except Exception as inner_e:
            logger.error(f"最终错误处理失败: {inner_e}")

if __name__ == '__main__':
    main()
