import { useApi } from "~/lib/hooks";
import { profiles } from "~/lib/api";
import type { Profile } from "~/lib/types";
import {
  Card,
  CardHeader,
  CardContent,
  EmptyState,
  ErrorState,
  Spinner,
  Button,
  Badge,
  SectionHeader,
  KPICard,
  StatBlock,
  Input,
  Label,
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  Textarea,
} from "~/components/ui";

export function ProfilePage() {
  const { data: profileData, loading: profileLoading, error: profileError, refetch: refetchProfile } = useApi(
    () => profiles.get(1), // Assuming single profile for now
    [],
  );

  // Editing state
  const [editing, setEditing] = React.useState(false);

  // Form state initialized from loaded profile
  const [formData, setFormData] = React.useState<Profile>({
    id: 1,
    name: profileData?.name || "",
    email: profileData?.email || "",
    phone: profileData?.phone || null,
    linkedin_url: profileData?.linkedin_url || null,
    github_url: profileData?.github_url || null,
    portfolio_url: profileData?.portfolio_url || null,
    headline: profileData?.headline || null,
    bio: profileData?.bio || null,
    current_city: profileData?.current_city || null,
    preferred_cities: profileData?.preferred_cities || null,
    geographic_preference: profileData?.geographic_preference || null,
    degree: profileData?.degree || null,
    field_of_study: profileData?.field_of_study || null,
    institution: profileData?.institution || null,
    graduation_year: profileData?.graduation_year || null,
    skills_summary: profileData?.skills_summary || null,
    preferred_role_types: profileData?.preferred_role_types || null,
    minimum_compensation: profileData?.minimum_compensation || null,
    availability_start: profileData?.availability_start || null,
    availability_end: profileData?.availability_end || null,
    work_arrangement: profileData?.work_arrangement || null,
    notable_achievements: profileData?.notable_achievements || null,
  });

  // Keep form in sync when profile data refetches (non-editing mode)
  React.useEffect(() => {
    if (!editing) {
      setFormData(prev => ({
        ...prev,
        name: profileData?.name || "",
        email: profileData?.email || "",
        phone: profileData?.phone,
        linkedin_url: profileData?.linkedin_url,
        github_url: profileData?.github_url,
        portfolio_url: profileData?.portfolio_url,
        headline: profileData?.headline,
        bio: profileData?.bio,
        current_city: profileData?.current_city,
        preferred_cities: profileData?.preferred_cities,
        geographic_preference: profileData?.geographic_preference,
        degree: profileData?.degree,
        field_of_study: profileData?.field_of_study,
        institution: profileData?.institution,
        graduation_year: profileData?.graduation_year,
        skills_summary: profileData?.skills_summary,
        preferred_role_types: profileData?.preferred_role_types,
        minimum_compensation: profileData?.minimum_compensation,
        availability_start: profileData?.availability_start,
        availability_end: profileData?.availability_end,
        work_arrangement: profileData?.work_arrangement,
        notable_achievements: profileData?.notable_achievements,
      }));
    }
  }, [profileData, editing]);

  // Handle input/change events
  const onChange = React.useCallback((e: React.ChangeEvent) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  }, []);

  // Handle graduation year and numeric fields change
  const onNumberChange = React.useCallback((e: React.ChangeEvent) => {
    const { name, value } = e.target;
    const numValue = value ? Number(value) : null;
    setFormData(prev => ({
      ...prev,
      [name]: numValue,
    }));
  }, []);

  // Handle form submission
  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await profiles.update(formData.id, {
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
      });
      setEditing(false);
      refetchProfile();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Unknown error";
      // We'll display the error via the ErrorState component below
      setEditing(false); // Reset editing state even on error
    }
  };

  // If no profile data and not editing, show empty state
  if (!profileData && !editing) {
    return <EmptyState title="No profile found" description="Create your profile to get started." />;
  }

  if (profileLoading && !editing) {
    return <Spinner />;
  }

  if (profileError && !editing) {
    return <ErrorState message={profileError} onRetry={refetchProfile} />;
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Profile</h1>
        <p className="text-sm text-gray-500 mt-1">Your opportunity operating system profile</p>
      </div>

      {/* Profile Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <KPICard label="Name" value={formData.name} icon="👤" color="blue" />
        <KPICard label="Email" value={formData.email} icon="✉️" color="green" />
        <KPICard label="Phone" value={formData.phone || "Not provided"} icon="📞" color="amber" />
        <KPICard label="GitHub" value={formData.github_url || "Not provided"} icon="octicon-mark-github" color="purple" />
        <KPICard label="LinkedIn" value={formData.linkedin_url || "Not provided"} icon="linkedin" color="indigo" />
        <KPICard label="Portfolio" value={formData.portfolio_url || "Not provided"} icon="globe" color="teal" />
      </div>

      {/* Detailed Info Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Details</h2>
            <Badge variant="secondary">{editing ? "Saving..." : "Edit profile"}</Badge>
          </div>
        </CardHeader>
        <CardContent>
          {editing ? (
            <EditProfileForm
              formData={formData}
              onChange={onChange}
              onNumberChange={onNumberChange}
              onSubmit={onSubmit}
              onCancel={setEditing}
            />
          ) : (
            <ViewProfileDetails profile={formData} />
          )}
        </CardContent>
      </Card>

      {/* Action buttons */}
      <div className="mt-6">
        {editing ? (
          <Button
            disabled={profileLoading}
            className="bg-blue-600 text-white hover:bg-blue-700"
          >
            Saving…
          </Button>
        ) : (
          <Button
            onClick={() => setEditing(true)}
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
  onChange,
  onNumberChange,
  onSubmit,
  onCancel,
}: {
  formData: Profile;
  onChange: React.ChangeEventHandler;
  onNumberChange: React.ChangeEventHandler;
  onSubmit: (e: React.FormEvent) => void;
  onCancel: () => void;
}) {
  return (
    <form onSubmit={onSubmit} className="space-y-4 max-w-lg">
      <Input
        name="name"
        placeholder="Full name"
        value={formData.name}
        onChange={onChange}
        required
      />
      <Input
        name="email"
        type="email"
        placeholder="Email address"
        value={formData.email}
        onChange={onChange}
        required
      />
      <Input
        name="phone"
        placeholder="Phone (optional)"
        value={formData.phone || ""}
        onChange={onChange}
      />
      <Input
        name="linkedin_url"
        placeholder="LinkedIn URL (optional)"
        value={formData.linkedin_url || ""}
        onChange={onChange}
      />
      <Input
        name="github_url"
        placeholder="GitHub URL (optional)"
        value={formData.github_url || ""}
        onChange={onChange}
      />
      <Input
        name="portfolio_url"
        placeholder="Portfolio URL (optional)"
        value={formData.portfolio_url || ""}
        onChange={onChange}
      />
      <Input
        name="headline"
        placeholder="Headline (optional)"
        value={formData.headline || ""}
        onChange={onChange}
      />
      <Textarea
        name="bio"
        rows={3}
        placeholder="Bio (optional)"
        value={formData.bio || ""}
        onChange={onChange}
      />
      {/* Geographic preferences */}
      <div className="space-y-2">
        <Label>Current city (optional)</Label>
        <Input
          name="current_city"
          placeholder="e.g., San Francisco"
          value={formData.current_city || ""}
          onChange={onChange}
        />
        <Label>Preferred cities (optional, comma-separated)</Label>
        <Input
          name="preferred_cities"
          placeholder="e.g., San Francisco, New York"
          value={formData.preferred_cities || ""}
          onChange={onChange}
        />
        <Label>Geographic preference (optional)</Label>
        <Input
          name="geographic_preference"
          placeholder="e.g., worldwide, remote"
          value={formData.geographic_preference || ""}
          onChange={onChange}
        />
      </div>
      {/* Education */}
      <div className="space-y-2">
        <Label>Degree (optional)</Label>
        <Input
          name="degree"
          placeholder="e.g., M.S. Computer Science"
          value={formData.degree || ""}
          onChange={onChange}
        />
        <Label>Field of study (optional)</Label>
        <Input
          name="field_of_study"
          placeholder="e.g., Artificial Intelligence"
          value={formData.field_of_study || ""}
          onChange={onChange}
        />
        <Label>Institution (optional)</Label>
        <Input
          name="institution"
          placeholder="e.g., Stanford University"
          value={formData.institution || ""}
          onChange={onChange}
        />
        <Label>Graduation year (optional)</Label>
        <Input
          name="graduation_year"
          type="number"
          placeholder="e.g., 2020"
          value={formData.graduation_year !== null ? String(formData.graduation_year) : ""}
          onChange={onNumberChange}
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
          onChange={onChange}
        />
      </div>
      {/* Professional preferences */}
      <div className="space-y-2">
        <Label>Preferred role types (optional, comma-separated)</Label>
        <Input
          name="preferred_role_types"
          placeholder="e.g., FULL_TIME, CONTRACT, STARTUP"
          value={formData.preferred_role_types || ""}
          onChange={onChange}
        />
        <Label>Minimum compensation (optional)</Label>
        <Input
          name="minimum_compensation"
          placeholder="e.g., 120000 INR"
          value={formData.minimum_compensation || ""}
          onChange={onChange}
        />
        <Label>Availability start (optional, timestamp)</Label>
        <Input
          name="availability_start"
          type="number"
          placeholder="e.g., 1704067200"
          value={formData.availability_start !== null ? String(formData.availability_start) : ""}
          onChange={onNumberChange}
        />
        <Label>Availability end (optional, timestamp)</Label>
        <Input
          name="availability_end"
          type="number"
          placeholder="e.g., 1893456000"
          value={formData.availability_end !== null ? String(formData.availability_end) : ""}
          onChange={onNumberChange}
        />
        <Label>Work arrangement (optional)</Label>
        <Input
          name="work_arrangement"
          placeholder="e.g., FULL_TIME, REMOTE, HYBRID"
          value={formData.work_arrangement || ""}
          onChange={onChange}
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
          onChange={onChange}
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