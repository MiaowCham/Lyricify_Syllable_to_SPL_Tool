import os
import re
from github import Github
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def convert_ms(ms, offset=0):
    adjusted = int(ms) + offset
    adjusted = max(adjusted, 0)
    minutes, ms = divmod(adjusted, 60000)
    seconds, milliseconds = divmod(ms, 1000)
    return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

def parse_issue_content(content):
    """增强型内容解析"""
    # 匹配offset（支持空行和注释）
    offset_match = re.search(r'^### offset\s*[\r\n]+([-\d]+)', content, re.MULTILINE)
    # 匹配歌词内容（支持多行和特殊字符）
    lys_match = re.search(r'^### LYS 歌词\s*[\r\n]+((?:\[.*?\].*?(?:\r?\n|$))+)', content, re.MULTILINE | re.DOTALL)
    
    offset = int(offset_match.group(1).strip()) if (offset_match and offset_match.group(1)) else 0
    lys_content = lys_match.group(1).strip() if (lys_match and lys_match.group(1)) else ''
    return offset, lys_content

def lys_to_spl(lys_text, time_offset=0):
    """完整保留格式的转换核心"""
    spl_lines = []
    # 增强正则（支持嵌套括号和换行）
    line_pattern = re.compile(r'^\[(\d+)\](.*?)(?=\[\d+\]|$)', re.MULTILINE | re.DOTALL)
    word_pattern = re.compile(r'([^\n\(]*?)\s*\((\d+),(\d+)\)', re.DOTALL)
    
    for line in [l.strip() for l in lys_text.split('\n') if l.strip()]:
        if not line.startswith('['):
            continue
            
        # 提取行内容
        content_match = line_pattern.match(line)
        if not content_match:
            continue
            
        content = content_match.group(2)
        word_entries = word_pattern.findall(content)
        
        segments = []
        last_end = 0
        for idx, (word, s, d) in enumerate(word_entries):
            start = int() + time_offset
            end = int() + int(d) + time_offset
            
            # 保留原始格式（含空格和括号）
            clean_word = word.replace('\n', ' ').replace('\r', '')
            segments.append(f"[{convert_ms(start)}]{clean_word}")
            
            # 添加间隔时间戳
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
    token = os.getenv('GITHUB_TOKEN')
    issue_number = int(os.getenv('ISSUE_NUMBER'))
    repo_name = os.getenv('GITHUB_REPOSITORY')

    if not all([token, issue_number, repo_name]):
        logger.error("缺少环境变量")
        return

    try:
        g = Github(token)
        repo = g.get_repo(repo_name)
        issue = repo.get_issue(number=issue_number)
        
        # 调试日志
        logger.info(f"原始Issue内容:\n{issue.body}")
        
        offset, lys_content = parse_issue_content(issue.body)
        logger.info(f"解析结果 - offset: {offset}, 歌词长度: {len(lys_content)}")
        
        if not lys_content:
            issue.create_comment("错误：未找到有效的LYS歌词内容")
            return

        try:
            spl_output = lys_to_spl(lys_content, offset)
            logger.info(f"转换结果:\n{spl_output}")
            comment = f"**输出:**\n```\n{spl_output}\n```"
        except Exception as e:
            logger.exception("转换失败")
            comment = f"错误：歌词转换失败 - {str(e)}"

        issue.create_comment(comment)
        logger.info("处理完成")

    except Exception as e:
        logger.exception("主流程异常")
        try:
            issue.create_comment(f"系统错误：{str(e)}")
        except Exception as inner_e:
            logger.error(f"评论失败: {inner_e}")

if __name__ == '__main__':
    main()
