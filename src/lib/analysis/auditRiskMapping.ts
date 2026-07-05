import type { AuditRiskMapping } from "@/types/analysis";
import type { StandardAccountKey } from "@/types/financial";

export const auditRiskMapping: Partial<Record<StandardAccountKey, AuditRiskMapping>> = {
  accountsReceivable: {
    accountName: "매출채권",
    risk: "회수가능성 저하 또는 수익인식 위험",
    assertions: ["실재성", "평가", "기간귀속"],
    procedures: ["외부조회", "후속 회수 검토", "매출 컷오프 테스트"]
  },
  inventory: {
    accountName: "재고자산",
    risk: "진부화 또는 평가손실 가능성",
    assertions: ["실재성", "평가"],
    procedures: ["재고실사 입회", "순실현가능가치 검토"]
  },
  intangibleAssets: {
    accountName: "무형자산",
    risk: "개발비 자본화 오류 가능성",
    assertions: ["발생", "평가"],
    procedures: ["자본화 요건 검토", "손상검토"]
  }
};
