import os
import re
from github import Github
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_issue_body(body):
    """解析Issue内容并提取参数"""
    params = {
        'offset': 0,
        'lys_content': ''
    }

    # 使用更健壮的正则表达式匹配
    offset_match = re.search(r'### offset\s*\n([\s\S]*?)(?=\n###|$)', body, re.IGNORECASE)
    lys_match = re.search(r'### LYS 歌词\s*\n([\s\S]*?)(?=\n###|$)', body, re.IGNORECASE)

    # 处理offset
    if offset_match:
        offset_value = offset_match.group(1).strip()
        if offset_value.lower() != '_no response_':
            try:
                params['offset'] = int(offset_value)
            except ValueError:
                raise ValueError(f"无效的offset值: {offset_value}")

    # 处理LYS内容
    if lys_match:
        params['lys_content'] = lys_match.group(1).strip()

    return params

def main():
    """GitHub Issue处理主函数"""
    try:
        # 从环境变量获取GitHub信息
        token = os.getenv('GITHUB_TOKEN')
        issue_number = int(os.getenv('ISSUE_NUMBER'))
        repo_name = os.getenv('GITHUB_REPOSITORY')

        if not all([token, issue_number, repo_name]):
            logger.error("缺少必要的环境变量")
            return

        # 初始化GitHub连接
        g = Github(token)
        repo = g.get_repo(repo_name)
        issue = repo.get_issue(number=issue_number)

        # 解析Issue内容
        try:
            params = parse_issue_body(issue.body)
        except Exception as e:
            issue.create_comment(f"❌ 参数解析错误: {str(e)}")
            return

        # 检查LYS内容
        if not params['lys_content']:
            issue.create_comment("❌ 未找到有效的LYS歌词内容")
            return

        # 转换歌词
        try:
            spl_content = lys_to_spl(params['lys_content'], params['offset'])
        except Exception as e:
            logger.exception("歌词转换失败")
            issue.create_comment(f"❌ 歌词转换失败: {str(e)}")
            return

        # 构建评论内容
        comment = "**转换结果:**\n```\n" + spl_content + "\n```"
        
        # 添加评论（限制最大长度）
        max_length = 65536 - len("```\n```")  # GitHub评论长度限制
        if len(comment) > max_length:
            comment = f"⚠️ 输出过长（{len(comment)}字符），已截断\n" + \
                     "```\n" + spl_content[:max_length-100] + "\n...\n```"
        
        issue.create_comment(comment)
        logger.info("处理结果已提交到Issue")

    except Exception as e:
        logger.exception("处理流程失败")
        try:
            error_msg = f"🔥 系统错误: {str(e)}"[:2000]  # 限制错误信息长度
            issue.create_comment(error_msg)
        except Exception as inner_e:
            logger.error(f"无法提交错误评论: {inner_e}")

if __name__ == '__main__':
    main()
