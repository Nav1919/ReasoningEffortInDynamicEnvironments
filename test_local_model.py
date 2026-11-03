# imports
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


def main():
    # Ollama runs a server on our own computer
    # localhost means this request stays on this machine
    url = "http://localhost:11434/api/chat"

    # use the original Qwen3 model that supports thinking on and off
    # the shorter qwen3:4b name downloaded a thinking-only release
    # use this exact tag so both tests use the same hybrid model
    model = "qwen3:4b-q4_K_M"

    # use the same prompt for both modes
    # this is just a connection test, not a Freeway decision yet
    prompt = "What is 17 multiplied by 23? Give only the final number."

    # initialize a list to save the results of both calls
    results = []

    # test the same model with thinking off, then thinking on
    for thinking_enabled in [False, True]:
        # label the mode so we can identify its output and saved results
        mode = "thinking_on" if thinking_enabled else "thinking_off"
        print(f"\nTesting {mode}...", flush=True)

        # set up the request we will send to Ollama
        payload = {
            "model": model,
            "messages": [
                # send the exact same question in both modes
                {"role": "user", "content": prompt}
            ],

            # change only the thinking switch between our two requests
            # this model's built-in template handles the mode instructions
            # we don't need our custom model or manual prompt suffixes
            "think": thinking_enabled,

            # wait for one complete response instead of streamed chunks
            "stream": False,

            # keep the model loaded between our two calls
            "keep_alive": "5m",

            "options": {
                # keep the same sampling settings for this connection test
                "temperature": 0.6,
                "seed": 0,

                # cap total generated tokens for this small test
                # this is a ceiling, not a reasoning-effort setting
                "num_predict": 2048,

                # limit the context size for our initial local test
                "num_ctx": 4096,
            },
        }

        # turn the Python dictionary into JSON bytes
        # this is the format the HTTP server expects
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        # start a clock before sending the request
        # perf_counter measures elapsed time reliably
        start = time.perf_counter()

        # send the request and read the full response
        # stop waiting after 180 seconds if the request doesn't finish
        # errors will stop the script so we can investigate them
        with urlopen(request, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))

        elapsed_seconds = time.perf_counter() - start

        # get the final answer and the separate thinking text
        # also inspect the printed answer for reasoning that leaked into it
        # an empty thinking field alone doesn't prove thinking was disabled
        message = result.get("message", {})
        answer = message.get("content", "")
        thinking = message.get("thinking", "")

        # save the request settings and complete server response
        # the response includes token counts and server timing fields
        results.append({
            "mode": mode,
            "request": payload,
            "latency_seconds": elapsed_seconds,
            "response": result,
        })

        print("Answer:", answer)
        print("Thinking text present:", bool(thinking.strip()))
        print("Elapsed seconds:", round(elapsed_seconds, 2))

        # eval_count is total generated tokens
        # don't label it as reasoning-only tokens
        print("Generated tokens:", result.get("eval_count"))
        print("Finish reason:", result.get("done_reason"))

        # the first request might include loading the model into memory
        # print that separately so we don't mistake loading for reasoning
        # Ollama reports this duration in nanoseconds, so convert to seconds
        load_duration = result.get("load_duration")
        if load_duration is not None:
            print("Model load seconds:", round(load_duration / 1_000_000_000, 2))

        # a token limit can cut off generation before the final answer
        if result.get("done_reason") == "length":
            print("Token limit reached; the response may be incomplete.")

    # create the same local logs folder used by our Freeway runner
    log_directory = Path(__file__).resolve().parent / "logs"
    log_directory.mkdir(exist_ok=True)

    # give this test its own timestamped filename
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    log_path = log_directory / f"local_model_test_{timestamp}.json"

    # save both responses so we can inspect them in VS Code
    with log_path.open("w", encoding="utf-8") as file:
        json.dump(results, file, indent=2)

    print("\nLog saved to:", log_path)


# only start the test when we run this file directly
if __name__ == "__main__":
    main()