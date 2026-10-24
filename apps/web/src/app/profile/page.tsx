"use client";

import React from "react";
import { useApi } from "@/lib/hooks";
import { profiles } from "@/lib/api";
import type { Profile } from "@/lib/types";
import {
  Card,
  CardHeader,
  CardContent,
  EmptyState,
  ErrorState,
  Spinner,
  Button,
  Badge,
  KPICard,
  Input,
  Label,
  Textarea,
} from "@/components/ui";

// Blank form used as the create-profile starting point.
const EMPTY_FORM: Profile = {
  id: 0,
  name: "",
  email: "",
  phone: null,
  linkedin_url: null,
  github_url: null,
  portfolio_url: null,
  headline: null,
  bio: null,
  created_at: "",
  updated_at: "",
  current_city: null,
  preferred_cities: null,
  geographic_preference: null,
  degree: null,
  field_of_study: null,
  institution: null,
  graduation_year: null,
  skills_summary: null,
  preferred_role_types: null,
  minimum_compensation: null,
  availability_start: null,
  availability_end: null,
  work_arrangement: null,
  notable_achievements: null,
};

// Fields stored as integers by the API; converted inside onField.
const NUMERIC_FIELDS = new Set([
  "graduation_year",
  "availability_start",
  "availability_end",
]);

export function ProfilePage() {
  // Single-user app: the owner profile is the first row of the list. Loading
  // the list (instead of a hardcoded id) lets a fresh install create its
  // first profile instead of hitting a 404.
  const {
    data: profileList,
    loading: profileLoading,
    error: profileError,
    refetch: refetchProfile,
  } = useApi(() => profiles.list(), []);

  const profileData = profileList?.[0] ?? null;

  // Editing / creating state
  const [editing, setEditing] = React.useState(false);
  const [creating, setCreating] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [formError, setFormError] = React.useState<string | null>(null);

  // Form state — seeded blank and filled only when entering edit/create
  // mode (see startEdit/startCreate below), so fetched data never needs an
  // effect to sync into state.
  const [formData, setFormData] = React.useState<Profile>(EMPTY_FORM);

  // Entering edit mode snapshots the loaded profile into the form.
  const startEdit = React.useCallback(() => {
    if (!profileData) return;
    setFormError(null);
    setFormData({ ...EMPTY_FORM, ...profileData });
    setEditing(true);
  }, [profileData]);

  // Entering create mode starts from a blank form. The profile row is
  // created only on explicit submit — never on render — so no duplicates.
  const startCreate = React.useCallback(() => {
    setFormError(null);
    setFormData(EMPTY_FORM);
    setCreating(true);
  }, []);

  // Generic field update matching the shared Input/Textarea API (their
  // onChange delivers the string value, not a DOM event). Numeric fields
  // are converted here so the forms stay declarative.
  const onField = React.useCallback((name: string, value: string) => {
    setFormData((prev) => ({
      ...prev,
      [name]: NUMERIC_FIELDS.has(name)
        ? value
          ? Number(value)
          : null
        : value || null,
    }));
  }, []);

  // Payload shared by edit and create — only fields the API accepts.
  const formPayload = React.useCallback(
    () => ({
      name: formData.name,
      email: formData.email,
      phone: formData.phone,
      linkedin_url: formData.linkedin_url,
      github_url: formData.github_url,
      portfolio_url: formData.portfolio_url,
      headline: formData.headline,
      bio: formData.bio,
      current_city: formData.current_city,
      preferred_cities: formData.preferred_cities,
      geographic_preference: formData.geographic_preference,
      degree: formData.degree,
      field_of_study: formData.field_of_study,
      institution: formData.institution,
      graduation_year: formData.graduation_year,
      skills_summary: formData.skills_summary,
      preferred_role_types: formData.preferred_role_types,
      minimum_compensation: formData.minimum_compensation,
      availability_start: formData.availability_start,
      availability_end: formData.availability_end,
      work_arrangement: formData.work_arrangement,
      notable_achievements: formData.notable_achievements,
    }),
    [formData],
  );

  // Edit submission — updates the existing profile by its real id.
  const onSubmitEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profileData) return;
    setSaving(true);
    setFormError(null);
    try {
      await profiles.update(profileData.id, formPayload());
      setEditing(false);
      refetchProfile();
    } catch (err: unknown) {
      // Keep the form open on error so input is not lost.
      setFormError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSaving(false);
    }
  };

  // Create submission — the only place a profile row is ever created.
  const onSubmitCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setFormError(null);
    try {
      await profiles.create(formPayload());
      setCreating(false);
      refetchProfile();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSaving(false);
    }
  };

  if (profileLoading) return <Spinner />;

  if (profileError && !creating) {
    return <ErrorState message={profileError} onRetry={refetchProfile} />;
  }

  // First-profile flow: nothing exists yet, offer a one-time create form.
  if (!profileData && !creating) {
    return (
      <div className="max-w-7xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Profile</h1>
          <p className="text-sm text-gray-500 mt-1">
            Your opportunity operating system profile
          </p>
        </div>
        <EmptyState
          title="No profile yet"
          description="This is a single-user app. Create your owner profile to get started — it is what opportunity matching runs against."
          action={
            <Button
              onClick={startCreate}
              className="bg-blue-600 text-white hover:bg-blue-700"
            >
              Create profile
            </Button>
          }
        />
      </div>
    );
  }

  if (!profileData && creating) {
    return (
      <div className="max-w-7xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Create your profile</h1>
          <p className="text-sm text-gray-500 mt-1">
            Only name and email are required — everything else can be added later.
          </p>
        </div>
        <Card className="max-w-lg">
          <CardContent>
            <CreateProfileForm
              formData={formData}
              onField={onField}
              onSubmit={onSubmitCreate}
              onCancel={() => setCreating(false)}
              saving={saving}
              error={formError}
            />
          </CardContent>
        </Card>
      </div>
    );
  }

  // View/edit always render from the loaded profile; while editing, the
  // live form takes over so the summary updates as you type.
  const display: Profile = editing ? formData : (profileData as Profile);

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Profile</h1>
        <p className="text-sm text-gray-500 mt-1">Your opportunity operating system profile</p>
      </div>

      {/* Profile Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <KPICard label="Name" value={display.name} icon="👤" color="blue" />
        <KPICard label="Email" value={display.email} icon="✉️" color="green" />
        <KPICard label="Phone" value={display.phone || "Not provided"} icon="📞" color="amber" />
        <KPICard label="GitHub" value={display.github_url || "Not provided"} icon="octicon-mark-github" color="purple" />
        <KPICard label="LinkedIn" value={display.linkedin_url || "Not provided"} icon="linkedin" color="indigo" />
        <KPICard label="Portfolio" value={display.portfolio_url || "Not provided"} icon="globe" color="teal" />
      </div>

      {/* Detailed Info Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Details</h2>
            <Badge variant="muted">{editing ? "Saving..." : "Edit profile"}</Badge>
          </div>
        </CardHeader>
        <CardContent>
          {editing ? (
            <EditProfileForm
              formData={formData}
              onField={onField}
              onSubmit={onSubmitEdit}
              onCancel={() => setEditing(false)}
            />
          ) : (
            <ViewProfileDetails profile={display} />
          )}
        </CardContent>
      </Card>

      {/* Action buttons */}
      <div className="mt-6 space-y-2">
        {formError && <p className="text-sm text-red-600">{formError}</p>}
        {editing ? (
          <Button
            disabled={saving}
            loading={saving}
            className="bg-blue-600 text-white hover:bg-blue-700"
          >
            {saving ? "Saving…" : "Save changes"}
          </Button>
        ) : (
          <Button
            onClick={startEdit}
            className="bg-blue-600 text-white hover:bg-blue-700"
          >
            Edit Profile
          </Button>
        )}
      </div>
    </div>
  );
}

function EditProfileForm({
  formData,
  onField,
  onSubmit,
  onCancel,
}: {
  formData: Profile;
  onField: (name: string, value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  onCancel: () => void;
}) {
  return (
    <form onSubmit={onSubmit} className="space-y-4 max-w-lg">
      <Input
        name="name"
        placeholder="Full name"
        value={formData.name}
        onChange={(v) => onField("name", v)}
        required
      />
      <Input
        name="email"
        type="email"
        placeholder="Email address"
        value={formData.email}
        onChange={(v) => onField("email", v)}
        required
      />
      <Input
        name="phone"
        placeholder="Phone (optional)"
        value={formData.phone || ""}
        onChange={(v) => onField("phone", v)}
      />
      <Input
        name="linkedin_url"
        placeholder="LinkedIn URL (optional)"
        value={formData.linkedin_url || ""}
        onChange={(v) => onField("linkedin_url", v)}
      />
      <Input
        name="github_url"
        placeholder="GitHub URL (optional)"
        value={formData.github_url || ""}
        onChange={(v) => onField("github_url", v)}
      />
      <Input
        name="portfolio_url"
        placeholder="Portfolio URL (optional)"
        value={formData.portfolio_url || ""}
        onChange={(v) => onField("portfolio_url", v)}
      />
      <Input
        name="headline"
        placeholder="Headline (optional)"
        value={formData.headline || ""}
        onChange={(v) => onField("headline", v)}
      />
      <Textarea
        name="bio"
        rows={3}
        placeholder="Bio (optional)"
        value={formData.bio || ""}
        onChange={(v) => onField("bio", v)}
      />
      {/* Geographic preferences */}
      <div className="space-y-2">
        <Label>Current city (optional)</Label>
        <Input
          name="current_city"
          placeholder="e.g., San Francisco"
          value={formData.current_city || ""}
          onChange={(v) => onField("current_city", v)}
        />
        <Label>Preferred cities (optional, comma-separated)</Label>
        <Input
          name="preferred_cities"
          placeholder="e.g., San Francisco, New York"
          value={formData.preferred_cities || ""}
          onChange={(v) => onField("preferred_cities", v)}
        />
        <Label>Geographic preference (optional)</Label>
        <Input
          name="geographic_preference"
          placeholder="e.g., worldwide, remote"
          value={formData.geographic_preference || ""}
          onChange={(v) => onField("geographic_preference", v)}
        />
      </div>
      {/* Education */}
      <div className="space-y-2">
        <Label>Degree (optional)</Label>
        <Input
          name="degree"
          placeholder="e.g., M.S. Computer Science"
          value={formData.degree || ""}
          onChange={(v) => onField("degree", v)}
        />
        <Label>Field of study (optional)</Label>
        <Input
          name="field_of_study"
          placeholder="e.g., Artificial Intelligence"
          value={formData.field_of_study || ""}
          onChange={(v) => onField("field_of_study", v)}
        />
        <Label>Institution (optional)</Label>
        <Input
          name="institution"
          placeholder="e.g., Stanford University"
          value={formData.institution || ""}
          onChange={(v) => onField("institution", v)}
        />
        <Label>Graduation year (optional)</Label>
        <Input
          name="graduation_year"
          type="number"
          placeholder="e.g., 2020"
          value={formData.graduation_year !== null ? String(formData.graduation_year) : ""}
          onChange={(v) => onField("graduation_year", v)}
        />
      </div>
      {/* Skills */}
      <div className="space-y-2">
        <Label>Skills summary (optional)</Label>
        <Textarea
          name="skills_summary"
          rows={3}
          placeholder="e.g., Python, React, Machine Learning"
          value={formData.skills_summary || ""}
          onChange={(v) => onField("skills_summary", v)}
        />
      </div>
      {/* Professional preferences */}
      <div className="space-y-2">
        <Label>Preferred role types (optional, comma-separated)</Label>
        <Input
          name="preferred_role_types"
          placeholder="e.g., FULL_TIME, CONTRACT, STARTUP"
          value={formData.preferred_role_types || ""}
          onChange={(v) => onField("preferred_role_types", v)}
        />
        <Label>Minimum compensation (optional)</Label>
        <Input
          name="minimum_compensation"
          placeholder="e.g., 120000 INR"
          value={formData.minimum_compensation || ""}
          onChange={(v) => onField("minimum_compensation", v)}
        />
        <Label>Availability start (optional, timestamp)</Label>
        <Input
          name="availability_start"
          type="number"
          placeholder="e.g., 1704067200"
          value={formData.availability_start !== null ? String(formData.availability_start) : ""}
          onChange={(v) => onField("availability_start", v)}
        />
        <Label>Availability end (optional, timestamp)</Label>
        <Input
          name="availability_end"
          type="number"
          placeholder="e.g., 1893456000"
          value={formData.availability_end !== null ? String(formData.availability_end) : ""}
          onChange={(v) => onField("availability_end", v)}
        />
        <Label>Work arrangement (optional)</Label>
        <Input
          name="work_arrangement"
          placeholder="e.g., FULL_TIME, REMOTE, HYBRID"
          value={formData.work_arrangement || ""}
          onChange={(v) => onField("work_arrangement", v)}
        />
      </div>
      {/* Achievements */}
      <div className="space-y-2">
        <Label>Notable achievements (optional)</Label>
        <Textarea
          name="notable_achievements"
          rows={3}
          placeholder="e.g., Awarded Employee of the Year, Published research paper"
          value={formData.notable_achievements || ""}
          onChange={(v) => onField("notable_achievements", v)}
        />
      </div>
      <div className="flex gap-3">
        <Button type="button" onClick={onCancel} className="gray-200">
          Cancel
        </Button>
        <Button type="submit" className="bg-blue-600 text-white hover:bg-blue-700">
          Save changes
        </Button>
      </div>
    </form>
  );
}

function ViewProfileDetails({ profile }: { profile: Profile }) {
  return (
    <div>
      {profile.headline && (
        <div className="mb-4">
          <h3 className="font-medium text-gray-700">Headline</h3>
          <p className="text-gray-600 mt-1">{profile.headline}</p>
        </div>
      )}

      {profile.bio && (
        <div className="mb-4">
          <h3 className="font-medium text-gray-700">Bio</h3>
          <p className="text-gray-600 mt-1">{profile.bio}</p>
        </div>
      )}

      {profile.current_city && (
        <div className="mb-4">
          <h3 className="font-medium text-gray-700">Current City</h3>
          <p className="text-gray-600 mt-1">{profile.current_city}</p>
        </div>
      )}

      {profile.preferred_cities && (
        <div className="mb-4">
          <h3 className="font-medium text-gray-700">Preferred Cities</h3>
          <p className="text-gray-600 mt-1">{profile.preferred_cities}</p>
        </div>
      )}

      {profile.geographic_preference && (
        <div className="mb-4">
          <h3 className="font-medium text-gray-700">Geographic Preference</h3>
          <p className="text-gray-600 mt-1">{profile.geographic_preference}</p>
        </div>
      )}

      {profile.degree && (
        <div className="mb-4">
          <h3 className="font-medium text-gray-700">Degree</h3>
          <p className="text-gray-600 mt-1">{profile.degree}</p>
        </div>
      )}

      {profile.field_of_study && (
        <div className="mb-4">
          <h3 className="font-medium text-gray-700">Field of Study</h3>
          <p className="text-gray-600 mt-1">{profile.field_of_study}</p>
        </div>
      )}

      {profile.institution && (
        <div className="mb-4">
          <h3 className="font-medium text-gray-700">Institution</h3>
          <p className="text-gray-600 mt-1">{profile.institution}</p>
        </div>
      )}

      {profile.graduation_year && (
        <div>
          <h3 className="font-medium text-gray-700">Graduation Year</h3>
          <p className="text-gray-600 mt-1">{profile.graduation_year}</p>
        </div>
      )}

      {profile.skills_summary && (
        <div className="mb-4">
          <h3 className="font-medium text-gray-700">Skills Summary</h3>
          <p className="text-gray-600 mt-1">{profile.skills_summary}</p>
        </div>
      )}

      {profile.preferred_role_types && (
        <div className="mb-4">
          <h3 className="font-medium text-gray-700">Preferred Role Types</h3>
          <p className="text-gray-600 mt-1">{profile.preferred_role_types}</p>
        </div>
      )}

      {profile.minimum_compensation && (
        <div>
          <h3 className="font-medium text-gray-700">Minimum Compensation</h3>
          <p className="text-gray-600 mt-1">{profile.minimum_compensation}</p>
        </div>
      )}

      {profile.availability_start && (
        <div>
          <h3 className="font-medium text-gray-700">Availability Start</h3>
          <p className="text-gray-600 mt-1">
            {new Date(profile.availability_start * 1000).toLocaleDateString()}
          </p>
        </div>
      )}

      {profile.availability_end && (
        <div>
          <h3 className="font-medium text-gray-700">Availability End</h3>
          <p className="text-gray-600 mt-1">
            {new Date(profile.availability_end * 1000).toLocaleDateString()}
          </p>
        </div>
      )}

      {profile.work_arrangement && (
        <div>
          <h3 className="font-medium text-gray-700">Work Arrangement</h3>
          <p className="text-gray-600 mt-1">{profile.work_arrangement}</p>
        </div>
      )}

      {profile.notable_achievements && (
        <div>
          <h3 className="font-medium text-gray-700">Notable Achievements</h3>
          <p className="text-gray-600 mt-1 line-clamp-3">{profile.notable_achievements}</p>
        </div>
      )}
    </div>
  );
}
function CreateProfileForm({
  formData,
  onField,
  onSubmit,
  onCancel,
  saving,
  error,
}: {
  formData: Profile;
  onField: (name: string, value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  onCancel: () => void;
  saving: boolean;
  error: string | null;
}) {
  return (
    <form onSubmit={onSubmit} className="space-y-4">
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="space-y-2">
        <Label>Name</Label>
        <Input
          name="name"
          placeholder="Full name"
          value={formData.name}
          onChange={(v) => onField("name", v)}
          required
        />
      </div>
      <div className="space-y-2">
        <Label>Email</Label>
        <Input
          name="email"
          type="email"
          placeholder="Email address"
          value={formData.email}
          onChange={(v) => onField("email", v)}
          required
        />
      </div>
      <div className="space-y-2">
        <Label>Headline (optional)</Label>
        <Input
          name="headline"
          placeholder="e.g., Software Engineer | Python | ML"
          value={formData.headline || ""}
          onChange={(v) => onField("headline", v)}
        />
      </div>
      <div className="space-y-2">
        <Label>Current city (optional)</Label>
        <Input
          name="current_city"
          placeholder="e.g., Chennai"
          value={formData.current_city || ""}
          onChange={(v) => onField("current_city", v)}
        />
      </div>
      <div className="flex gap-3">
        <Button type="button" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          type="submit"
          disabled={saving}
          loading={saving}
          className="bg-blue-600 text-white hover:bg-blue-700"
        >
          {saving ? "Creating…" : "Create profile"}
        </Button>
      </div>
    </form>
  );
}

export default ProfilePage;
