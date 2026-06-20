import { getCurrentVersion, getPlanContent } from '../../utils/plan';
import type { TripPlanResponse, TripPlanVersionResponse } from '../../api/types';

describe('Plan Utilities', () => {
  const createMockPlan = (
    versionContent: any = {},
    versionId: number = 1
  ): TripPlanResponse => ({
    id: 1,
    owner_user_id: 1,
    title: 'Test Plan',
    city: 'Test City',
    start_date: '2026-05-01',
    end_date: '2026-05-05',
    budget_range: '中',
    created_at: '2026-05-01T00:00:00Z',
    updated_at: '2026-05-01T00:00:00Z',
    current_version_id: versionId,
    origin: null,
    current_version: {
      id: versionId,
      plan_id: 1,
      parent_version_id: null,
      owner_user_id: 1,
      version_no: 1,
      source_type: 'ai',
      change_summary: 'Initial plan',
      content_json: versionContent,
      created_at: '2026-05-01T00:00:00Z',
    } as TripPlanVersionResponse,
  });

  describe('getCurrentVersion', () => {
    it('should return current version when exists', () => {
      const plan = createMockPlan({ title: 'Test' });
      const version = getCurrentVersion(plan);
      expect(version).not.toBeNull();
      expect(version?.id).toBe(1);
    });

    it('should return null when no current version', () => {
      const planWithoutVersion = {
        ...createMockPlan(),
        current_version: null,
      } as TripPlanResponse;
      const version = getCurrentVersion(planWithoutVersion);
      expect(version).toBeNull();
    });
  });

  describe('getPlanContent', () => {
    it('should return plan content when exists', () => {
      const content = { title: 'Test Plan', city: 'Beijing' };
      const plan = createMockPlan(content);
      const result = getPlanContent(plan);
      expect(result).toEqual(content);
    });

    it('should return empty object when no content', () => {
      const plan = createMockPlan(null);
      const result = getPlanContent(plan);
      expect(result).toEqual({});
    });

    it('should return empty object when current version is null', () => {
      const planWithoutVersion = {
        ...createMockPlan(),
        current_version: null,
      } as TripPlanResponse;
      const result = getPlanContent(planWithoutVersion);
      expect(result).toEqual({});
    });
  });
});