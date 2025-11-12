# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "gradio",
#   "pymilvus[milvus_lite]",
#   "FlagEmbedding",
#   "tqdm",
#   "torch",
# ]
# ///

import gradio as gr
import subprocess
import urllib.parse
import os, json

GH_RAW = "https://raw.githubusercontent.com/gegedenice/uv-scripts/main"
DEFAULT_URI = os.environ.get("MILVUS_URI", "./milvus.db")

def run_inference(provider: str, hf_subpath: str, model: str, api_key: str, system_prompt: str, user_prompt: str, json_output: bool) -> str:
    """
    Runs LLM inference using the GH_RAW script.
    """
    # Construct the command
    command = [
        "uv", "run", f"{GH_RAW}/llms-openai-inference.py", "--",
        "--provider", provider,
    ]
    if provider == "huggingface":
        command.extend(["--hf-subpath", hf_subpath])

    command.extend([
        "--model", model,
        "--api-key", api_key,
        "-s", system_prompt,
        "-u", user_prompt,
    ])
    if json_output:
        command.append("--json-output")

    # Execute the command
    result = subprocess.run(command, capture_output=True, text=True)

    # Check for errors
    if result.returncode != 0:
        raise Exception(f"Script execution failed: {result.stderr}")

    # Parse the JSON output and extract the text if json_output is True
    if json_output:
        try:
            output_json = json.loads(result.stdout)
            llm_output = output_json.get("text", "")
            return llm_output
        except json.JSONDecodeError:
            raise Exception(f"Failed to parse JSON output: {result.stdout}")
    else:
        return result.stdout
  
def get_retrieved_chunks(query: str, k: int, collection_name: str) -> str:
    """
    Retrieves relevant chunks from Milvus using query_hybrid.py.
    """
    # Construct the command
    command = [
        "uv", "run", f"{GH_RAW}/RAG/query_hybrid.py", "--",
        "--collection", collection_name,
        "--milvus-uri", DEFAULT_URI,
        "--k", str(k),
        "--show-scores"
    ]

    # Execute the command
    result = subprocess.run(command, capture_output=True, text=True)

    # Check for errors
    if result.returncode != 0:
        raise Exception(f"Script execution failed: {result.stderr}")

    try:
        output_json = json.loads(result.stdout)
        passages = []
        for hit in output_json.get("results", []):
            passages.append(f'Contenu: {hit["text"]}\nSource: {hit["source"]}')
        return "\n\n".join(passages)
    except json.JSONDecodeError:
        raise Exception(f"Failed to parse JSON output: {result.stdout}")
  
def run_rag_query(query: str, provider: str, hf_subpath: str, model: str, api_key: str, system_prompt: str) -> tuple[str, str]:
    """
    Retrieves relevant chunks from Milvus and generates a response using the specified LLM.
    """
    k = 5  # Number of chunks to retrieve
    collection_name = "rapports"
    retrieved_chunks = get_retrieved_chunks(query, k, collection_name)

    user_prompt = f"""Question:
{query}

Utilise le contexte suivant pour répondre à la question :
{retrieved_chunks}
"""

    # Call inference with the combined prompt
    try:
        rag_answer = run_inference(provider, hf_subpath, model, api_key, system_prompt, user_prompt, json_output=False)
    except Exception as e:
        rag_answer = f"Error during inference: {str(e)}"

    return retrieved_chunks, rag_answer

def main():
    import argparse
    parser = argparse.ArgumentParser(description="RAG Query and LLM Inference Gradio App")
    parser.add_argument("--milvus-uri", default=DEFAULT_URI, help="Milvus DB URI (default from MILVUS_URI env or ./milvus.db)")
    args = parser.parse_args()
    
    # Update the global DEFAULT_URI for use in functions
    global DEFAULT_URI
    DEFAULT_URI = args.milvus_uri

    with gr.Blocks() as demo:
        gr.Markdown("## LLM Inference and RAG Query App")

        # Shared inference parameters
        provider_input = gr.Textbox(label="Provider (e.g., huggingface)", value="huggingface")
        hf_subpath_input = gr.Textbox(label="HF Subpath (if provider is huggingface)", value="novita/v3/openai")
        model_input = gr.Textbox(label="Model (e.g., moonshotai/kimi-k2-instruct)")
        token_input = gr.Textbox(label="API Token", type="password")

        with gr.Tab("LLM Inference"):
            system_prompt_input = gr.Textbox(label="System Prompt", lines=5)
            user_prompt_input = gr.Textbox(label="User Prompt", lines=5)
            json_output_checkbox = gr.Checkbox(label="JSON Output", value=False)
            inference_button = gr.Button("Run Inference")
            inference_output = gr.Textbox(label="Inference Output", lines=10)
            inference_button.click(
                run_inference,
                inputs=[provider_input, hf_subpath_input, model_input, token_input, system_prompt_input, user_prompt_input, json_output_checkbox],
                outputs=inference_output
            )

        with gr.Tab("RAG Query"):
            system_prompt_rag = gr.Textbox(label="System Prompt for RAG", lines=5, value="You are a helpful assistant.")
            rag_query_input = gr.Textbox(label="RAG Query", lines=5)
            rag_button = gr.Button("Run RAG")
            retrieved_chunks_output = gr.Textbox(label="Retrieved Chunks", lines=10)
            rag_answer_output = gr.Textbox(label="RAG Answer", lines=10)
            rag_button.click(
                run_rag_query,
                inputs=[rag_query_input, provider_input, hf_subpath_input, model_input, token_input, system_prompt_rag],
                outputs=[retrieved_chunks_output, rag_answer_output]
            )

        demo.launch(share=True)

if __name__ == "__main__":
    main()