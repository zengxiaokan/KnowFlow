import uuid

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:8000"
QUESTION = "Java 一共有多少类型的面试题？"


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        headless=True,
        executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    )
    page = browser.new_page()
    username = f"chat_e2e_{uuid.uuid4().hex[:10]}"
    captured_payloads = []

    def capture_question_request(request):
        if "/ask/" in request.url:
            captured_payloads.append(request.post_data or "")

    page.on("request", capture_question_request)

    page.goto(f"{BASE_URL}/accounts/signup/")
    page.wait_for_load_state("networkidle")
    page.locator("#id_username").fill(username)
    page.locator("#id_email").fill(f"{username}@example.com")
    page.locator("#id_password1").fill("KnowFlowE2E2026!")
    page.locator("#id_password2").fill("KnowFlowE2E2026!")
    page.get_by_role("button", name="创建并开始使用").click()
    page.wait_for_load_state("networkidle")

    page.get_by_role("button", name="新建知识库").first.click()
    page.locator("#create-kb").wait_for(state="visible")
    page.locator("#create-kb input[name='name']").fill("问答提交回归测试")
    page.locator("#create-kb textarea[name='description']").fill("浏览器自动化测试")
    page.locator("#create-kb").get_by_role("button", name="创建知识库").click()
    page.wait_for_load_state("networkidle")

    question_input = page.locator("#question-input")
    question_input.fill(QUESTION)
    page.get_by_role("button", name="发送").click()
    page.wait_for_timeout(750)

    failure = page.get_by_text("提交失败：问题不能为空")
    if len(captured_payloads) != 1 or QUESTION not in captured_payloads[0]:
        raise AssertionError(f"请求未发送预期内容：{captured_payloads}")
    if failure.count() and failure.first.is_visible():
        raise AssertionError("页面显示问题不能为空，但输入框中提交了非空问题")
    if page.locator(".chat-message.user").count() != 1:
        raise AssertionError("前端没有渲染已提交的用户问题")
    print("chat-submit-ok")
    browser.close()
