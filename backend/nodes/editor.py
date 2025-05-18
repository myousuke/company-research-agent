from langchain_core.messages import AIMessage
from typing import Dict, Any
from openai import AsyncOpenAI
import os
import logging

logger = logging.getLogger(__name__)

from ..classes import ResearchState
from ..utils.references import format_references_section

class Editor:
    """Compiles individual section briefings into a cohesive final report."""
    
    def __init__(self) -> None:
        self.openai_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        # Configure OpenAI
        self.openai_client = AsyncOpenAI(api_key=self.openai_key)
        
        # Initialize context dictionary for use across methods
        self.context = {
            "company": "Unknown Company",
            "industry": "Unknown",
            "hq_location": "Unknown"
        }

    async def compile_briefings(self, state: ResearchState) -> ResearchState:
        """Compile individual briefing categories from state into a final report."""
        company = state.get('company', 'Unknown Company')
        
        # Update context with values from state
        self.context = {
            "company": company,
            "industry": state.get('industry', 'Unknown'),
            "hq_location": state.get('hq_location', 'Unknown')
        }
        
        # Send initial compilation status
        if websocket_manager := state.get('websocket_manager'):
            if job_id := state.get('job_id'):
                await websocket_manager.send_status_update(
                    job_id=job_id,
                    status="processing",
                    message=f"Starting report compilation for {company}",
                    result={
                        "step": "Editor",
                        "substep": "initialization"
                    }
                )

        context = {
            "company": company,
            "industry": state.get('industry', 'Unknown'),
            "hq_location": state.get('hq_location', 'Unknown')
        }
        
        msg = [f"📑 Compiling final report for {company}..."]
        
        # Pull individual briefings from dedicated state keys
        briefing_keys = {
            'company': 'company_briefing',
            'industry': 'industry_briefing',
            'financial': 'financial_briefing',
            'news': 'news_briefing'
        }

        # Send briefing collection status
        if websocket_manager := state.get('websocket_manager'):
            if job_id := state.get('job_id'):
                await websocket_manager.send_status_update(
                    job_id=job_id,
                    status="processing",
                    message="Collecting section briefings",
                    result={
                        "step": "Editor",
                        "substep": "collecting_briefings"
                    }
                )

        individual_briefings = {}
        for category, key in briefing_keys.items():
            if content := state.get(key):
                individual_briefings[category] = content
                msg.append(f"Found {category} briefing ({len(content)} characters)")
            else:
                msg.append(f"No {category} briefing available")
                logger.error(f"Missing state key: {key}")
        
        if not individual_briefings:
            msg.append("\n⚠️ No briefing sections available to compile")
            logger.error("No briefings found in state")
        else:
            try:
                compiled_report = await self.edit_report(state, individual_briefings, context)
                if not compiled_report or not compiled_report.strip():
                    logger.error("Compiled report is empty!")
                else:
                    logger.info(f"Successfully compiled report with {len(compiled_report)} characters")
            except Exception as e:
                logger.error(f"Error during report compilation: {e}")
        state.setdefault('messages', []).append(AIMessage(content="\n".join(msg)))
        return state
    
    async def edit_report(self, state: ResearchState, briefings: Dict[str, str], context: Dict[str, Any]) -> str:
        """Compile section briefings into a final report and update the state."""
        try:
            company = self.context["company"]
            
            # Step 1: Initial Compilation
            if websocket_manager := state.get('websocket_manager'):
                if job_id := state.get('job_id'):
                    await websocket_manager.send_status_update(
                        job_id=job_id,
                        status="processing",
                        message="Compiling initial research report",
                        result={
                            "step": "Editor",
                            "substep": "compilation"
                        }
                    )

            edited_report = await self.compile_content(state, briefings, company)
            if not edited_report:
                logger.error("Initial compilation failed")
                return ""

            # Step 2: Deduplication and Cleanup
            if websocket_manager := state.get('websocket_manager'):
                if job_id := state.get('job_id'):
                    await websocket_manager.send_status_update(
                        job_id=job_id,
                        status="processing",
                        message="Cleaning up and organizing report",
                        result={
                            "step": "Editor",
                            "substep": "cleanup"
                        }
                    )

            # Step 3: Formatting Final Report
            if websocket_manager := state.get('websocket_manager'):
                if job_id := state.get('job_id'):
                    await websocket_manager.send_status_update(
                        job_id=job_id,
                        status="processing",
                        message="Formatting final report",
                        result={
                            "step": "Editor",
                            "substep": "format"
                        }
                    )
            final_report = await self.content_sweep(state, edited_report, company)
            
            final_report = final_report or ""
            
            logger.info(f"Final report compiled with {len(final_report)} characters")
            if not final_report.strip():
                logger.error("Final report is empty!")
                return ""
            
            logger.info("Final report preview:")
            logger.info(final_report[:500])
            
            # Update state with the final report in two locations
            state['report'] = final_report
            state['status'] = "editor_complete"
            if 'editor' not in state or not isinstance(state['editor'], dict):
                state['editor'] = {}
            state['editor']['report'] = final_report
            logger.info(f"Report length in state: {len(state.get('report', ''))}")
            
            if websocket_manager := state.get('websocket_manager'):
                if job_id := state.get('job_id'):
                    await websocket_manager.send_status_update(
                        job_id=job_id,
                        status="editor_complete",
                        message="Research report completed",
                        result={
                            "step": "Editor",
                            "report": final_report,
                            "company": company,
                            "is_final": True,
                            "status": "completed"
                        }
                    )
            
            return final_report
        except Exception as e:
            logger.error(f"Error in edit_report: {e}")
            return ""
    
    async def compile_content(self, state: ResearchState, briefings: Dict[str, str], company: str) -> str:
        """Initial compilation of research sections."""
        combined_content = "\n\n".join(content for content in briefings.values())
        
        references = state.get('references', [])
        reference_text = ""
        if references:
            logger.info(f"Found {len(references)} references to add during compilation")
            
            # Get pre-processed reference info from curator
            reference_info = state.get('reference_info', {})
            reference_titles = state.get('reference_titles', {})
            
            logger.info(f"Reference info from state: {reference_info}")
            logger.info(f"Reference titles from state: {reference_titles}")
            
            # Use the references module to format the references section
            reference_text = format_references_section(references, reference_info, reference_titles)
            logger.info(f"Added {len(references)} references during compilation")
        
        # Use values from centralized context
        company = self.context["company"]
        industry = self.context["industry"]
        hq_location = self.context["hq_location"]
        
        prompt = f"""{company} に関する包括的な調査レポートを作成してください。以下は各セクションのブリーフィングです:
{combined_content}

{company} は日本の {industry} 企業で、本社は {hq_location} にあります。次の点に留意してレポートをまとめてください。
1. すべてのセクションの情報を統合し、重複を避ける
2. 各セクションの重要な内容を保持する
3. 論理的に整理し、不要なつなぎの説明を省く
4. 明確なセクション見出しと構成を使用する

書式ルール:
以下のドキュメント構成を厳密に守ってください。

# {company} 調査レポート

## 会社概要
[Company content with ### subsections]

## 業界概要
[Industry content with ### subsections]

## 財務概要
[Financial content with ### subsections]

## ニュース
[News content with ### subsections]

レポートはマークダウン形式で返してください。解説やコメントは不要です。"""
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {
                        "role": "system",
                        "content": "あなたはブリーフィングを統合して詳細なレポートを作成する専門編集者です。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0,
                stream=False
            )
            initial_report = response.choices[0].message.content.strip()
            
            # Append the references section after LLM processing
            if reference_text:
                initial_report = f"{initial_report}\n\n{reference_text}"
            
            return initial_report
        except Exception as e:
            logger.error(f"Error in initial compilation: {e}")
            return (combined_content or "").strip()
        
    async def content_sweep(self, state: ResearchState, content: str, company: str) -> str:
        """Sweep the content for any redundant information."""
        # Use values from centralized context
        company = self.context["company"]
        industry = self.context["industry"]
        hq_location = self.context["hq_location"]
        
        prompt = f"""あなたはブリーフィング編集の専門家です。以下は {company} に関するレポートです。

現在のレポート:
{content}

1. 重複した情報を削除する
2. {hq_location} に本社を置く日本の {industry} 企業 {company} に関係のない情報を除外する
3. 内容の薄いセクションを削除する
4. "ここにニュースがあります" のようなメタ的なコメントを除去する

次のドキュメント構成を厳密に守ってください:

## Company Overview
[Company content with ### subsections]

## Industry Overview
[Industry content with ### subsections]

## Financial Overview
[Financial content with ### subsections]

## News
[News content with ### subsections]

## References
[References in MLA format - PRESERVE EXACTLY AS PROVIDED]

重要なルール:
1. ドキュメントは必ず "# {company} 調査レポート" から始める
2. 使用できる ## 見出しは以下の順序のみ:
   - ## 会社概要
   - ## 業界概要
   - ## 財務概要
   - ## ニュース
   - ## References
3. 他の ## 見出しは使用不可
4. 会社・業界・財務の各セクションでは ### を使う
5. ニュースセクションは箇条書き(*)のみで見出しを使わない
6. コードブロック(```)は使用しない
7. セクション間の空行は1行まで
8. すべての箇条書きは * で始める
9. 各セクション/リストの前後には1行の空行を入れる
10. References セクションの形式は変更しない

整形済みのレポートをマークダウン形式で返してください。解説は不要です。

最終的なレポートのみを返答し、コメントは不要です。"""
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4.1-mini", 
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは文書構造を整える専門的なMarkdownフォーマッターです。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0,
                stream=True
            )
            
            accumulated_text = ""
            buffer = ""
            
            async for chunk in response:
                if chunk.choices[0].finish_reason == "stop":
                    websocket_manager = state.get('websocket_manager')
                    if websocket_manager and buffer:
                        job_id = state.get('job_id')
                        if job_id:
                            await websocket_manager.send_status_update(
                                job_id=job_id,
                                status="report_chunk",
                                message="Formatting final report",
                                result={
                                    "chunk": buffer,
                                    "step": "Editor"
                                }
                            )
                    break
                    
                chunk_text = chunk.choices[0].delta.content
                if chunk_text:
                    accumulated_text += chunk_text
                    buffer += chunk_text
                    
                    if any(char in buffer for char in ['.', '!', '?', '\n']) and len(buffer) > 10:
                        if websocket_manager := state.get('websocket_manager'):
                            if job_id := state.get('job_id'):
                                await websocket_manager.send_status_update(
                                    job_id=job_id,
                                    status="report_chunk",
                                    message="Formatting final report",
                                    result={
                                        "chunk": buffer,
                                        "step": "Editor"
                                    }
                                )
                        buffer = ""
            
            return (accumulated_text or "").strip()
        except Exception as e:
            logger.error(f"Error in formatting: {e}")
            return (content or "").strip()

    async def run(self, state: ResearchState) -> ResearchState:
        state = await self.compile_briefings(state)
        # Ensure the Editor node's output is stored both top-level and under "editor"
        if 'report' in state:
            if 'editor' not in state or not isinstance(state['editor'], dict):
                state['editor'] = {}
            state['editor']['report'] = state['report']
        return state
