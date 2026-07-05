export class AppError extends Error {
  code: string;
  status: number;

  constructor(message: string, code = "APP_ERROR", status = 500) {
    super(message);
    this.name = "AppError";
    this.code = code;
    this.status = status;
  }
}

export function toKoreanErrorMessage(error: unknown): string {
  if (error instanceof AppError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "알 수 없는 오류가 발생했습니다.";
}

export function createApiError(message: string, code: string, status = 400) {
  return new AppError(message, code, status);
}

export function requireValue(value: string | undefined, message: string, code: string) {
  if (!value) {
    throw new AppError(message, code, 500);
  }

  return value;
}
