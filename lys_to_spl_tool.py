import os
import re
from github import Github
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def convert_ms(ms, offset=0):
    """毫秒转时间戳（含偏移和负值保护）"""
    adjusted = int(ms) + offset
    adjusted = max(adjusted, 0)
    minutes, ms = divmod(adjusted, 60000)
    seconds, milliseconds = divmod(ms, 1000)
    return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

def parse_issue_content(content):
    """解析Issue内容提取offset和歌词"""
    offset_match = re.search(r'### offset\s+([\d-]+)', content)
    lys_match = re.search(r'### LYS 歌词\s+((?:\[.*?\].*?\n?)+)', content, re.DOTALL)
    
    offset = int(offset_match.group(1).strip()) if offset_match else 0
    lys_content = lys_match.group(1).strip() if lys_match else ''
    return offset, lys_content

def lys_to_spl(lys_text, time_offset=0):
    """增强版歌词转换核心逻辑"""
    spl_lines = []
    word_pattern = re.compile(r'(.*?)\s*\((\d+),(\d+)\)', re.DOTALL)
    
    for line in lys_text.split('\n'):
        line = line.strip()
        if not line.startswith('['):
            continue

        prop_match = re.match(r'\[(\d+)\](.*)', line)
        if not prop_match:
            continue
            
        content = prop_match.group(2)
        word_entries = word_pattern.findall(content)
        
        if not word_entries:
            continue

        segments = []
        last_end = 0
        for idx, (word, start_str, duration_str) in enumerate(word_entries):
            original_start = int(start_str)
            start = original_start + time_offset
            duration = int(duration_str)
            end = original_start + duration + time_offset
            
            # 保留原始空格和括号
            cleaned_word = word.replace('\n', ' ').strip('\r')
            segments.append(f"[{convert_ms(start)}]{cleaned_word}")
            
            # 检测间隔
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
    """GitHub集成主处理逻辑"""
    token = os.getenv('GITHUB_TOKEN')
    issue_number = int(os.getenv('ISSUE_NUMBER'))
    repo_name = os.getenv('GITHUB_REPOSITORY')

    if not all([token, issue_number, repo_name]):
        logger.error("Missing environment variables")
        return

    try:
        g = Github(token)
        repo = g.get_repo(repo_name)
        issue = repo.get_issue(number=issue_number)
        
        # 解析Issue内容
        offset, lys_content = parse_issue_content(issue.body)
        if not lys_content:
            issue.create_comment("错误：未找到有效的LYS歌词内容")
            return

        # 转换歌词
        try:
            spl_output = lys_to_spl(lys_content, offset)
            comment = f"**输出:**\n```\n{spl_output}\n```"
        except Exception as e:
            logger.exception("转换失败")
            comment = f"错误：歌词转换失败 - {str(e)}"

        # 提交评论
        issue.create_comment(comment)
        logger.info("处理结果已提交")

    except Exception as e:
        logger.exception("GitHub操作失败")
        try:
            issue.create_comment(f"系统错误：{str(e)}")
        except:
            pass

if __name__ == '__main__':
    main()
