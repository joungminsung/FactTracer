const httpStatusMessage: Record<number, string> = {
  401: "로그인 상태를 확인해 주세요.",
  403: "이 화면을 볼 권한이 없습니다.",
  404: "해당 항목을 찾을 수 없습니다.",
  409: "이미 처리된 항목입니다.",
  422: "입력한 내용을 다시 확인해 주세요.",
  500: "일시적으로 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.",
};

export function getHttpStatusMessage(status: number) {
  return (
    httpStatusMessage[status] ??
    (status >= 500
      ? "일시적으로 처리하지 못했습니다. 잠시 후 다시 시도해 주세요."
      : "요청을 처리하지 못했습니다.")
  );
}

export function getUserActionMessage(error: unknown, fallback: string) {
  if (
    typeof error === "object" &&
    error !== null &&
    "status" in error &&
    typeof error.status === "number"
  ) {
    return getHttpStatusMessage(error.status);
  }

  if (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    error.name === "AbortError"
  ) {
    return "처리 시간이 길어지고 있습니다. 잠시 후 다시 시도해 주세요.";
  }

  if (error instanceof Error) {
    if (
      error.message === "Failed to fetch" ||
      error.message === "Load failed" ||
      error.message.includes("NetworkError")
    ) {
      return "요청을 보낼 수 없습니다. 연결 상태를 확인한 뒤 다시 시도해 주세요.";
    }

    if (
      error.message.includes("NEXT_PUBLIC") ||
      error.message.includes("Bearer") ||
      error.message.includes("API") ||
      error.message.includes("URL")
    ) {
      return "현재 요청을 처리할 수 없습니다. 잠시 후 다시 시도해 주세요.";
    }

    return error.message;
  }

  return fallback;
}
