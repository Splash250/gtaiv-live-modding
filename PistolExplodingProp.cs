using System;
using GTA;

namespace LiveModding
{
    public class PistolExplodingPropScript : Script
    {
        private static readonly string[] PropModelCandidates =
        {
            "AMB_WATERCAN",
            "AMB_JUICE_BOT",
            "AMB_MILK",
            "AMB_BS_DRINK",
            "AMB_CAN_DRINK_1",
            "AMB_CAN_DRINK_2"
        };

        private const int ShotCooldownMs = 180;
        private const int MinimumArmTimeMs = 120;
        private const int MaxFlightTimeMs = 2500;
        private const float SpawnDistance = 1.25f;
        private const float SpawnHeightOffset = 0.1f;
        private const float LaunchSpeed = 24.0f;
        private const float ImpactSpeedThreshold = 1.5f;
        private const float ImpactMovementThreshold = 0.08f;
        private const float ExplosionPower = 5.5f;

        private string loadedPropModelName;
        private bool missingModelReported;
        private int nextAllowedShotTime;
        private ProjectileState activeProjectile;

        public PistolExplodingPropScript()
        {
            Interval = 0;
            Tick += new EventHandler(OnTick);
            Game.DisplayText("Pistol exploding prop loaded.", 3000);
        }

        private void OnTick(object sender, EventArgs e)
        {
            UpdateProjectile();

            Ped player = Player.Character;
            if (player == null)
            {
                return;
            }

            if (Game.GameTime < nextAllowedShotTime)
            {
                return;
            }

            if (!IsPistol(player.Weapons.CurrentType) || !player.isShooting)
            {
                return;
            }

            LaunchProjectile(player);
            nextAllowedShotTime = Game.GameTime + ShotCooldownMs;
        }

        private void LaunchProjectile(Ped player)
        {
            Model propModel = ResolvePropModel();
            if (!propModel.isValid)
            {
                if (!missingModelReported)
                {
                    Game.DisplayText("No small prop model found for pistol explosive.", 3000);
                    missingModelReported = true;
                }

                return;
            }

            CleanupProjectile(false);

            Vector3 aimDirection = GetAimDirection(player);
            Vector3 spawnPosition = player.Position + (aimDirection * SpawnDistance);
            spawnPosition.Z += SpawnHeightOffset;

            GTA.Object projectile = World.CreateObject(propModel, spawnPosition);
            if (projectile == null)
            {
                return;
            }

            projectile.Collision = true;
            projectile.Heading = aimDirection.ToHeading();
            projectile.Velocity = (aimDirection * LaunchSpeed) + player.Velocity;
            projectile.NoLongerNeeded();

            activeProjectile = new ProjectileState(projectile, Game.GameTime, projectile.Position);
        }

        private void UpdateProjectile()
        {
            if (activeProjectile == null)
            {
                return;
            }

            GTA.Object projectile = activeProjectile.Object;
            if (projectile == null || !projectile.Exists())
            {
                activeProjectile = null;
                return;
            }

            int age = Game.GameTime - activeProjectile.SpawnTime;
            Vector3 currentPosition = projectile.Position;
            float movementSinceLastTick = (currentPosition - activeProjectile.LastPosition).Length();
            float currentSpeed = projectile.Velocity.Length();

            if (age >= MaxFlightTimeMs)
            {
                CleanupProjectile(true);
                return;
            }

            if (age >= MinimumArmTimeMs &&
                (currentSpeed <= ImpactSpeedThreshold || movementSinceLastTick <= ImpactMovementThreshold))
            {
                CleanupProjectile(true);
                return;
            }

            activeProjectile.LastPosition = currentPosition;
        }

        private void CleanupProjectile(bool explode)
        {
            if (activeProjectile == null)
            {
                return;
            }

            GTA.Object projectile = activeProjectile.Object;
            Vector3 explosionPosition = activeProjectile.LastPosition;

            if (projectile != null && projectile.Exists())
            {
                explosionPosition = projectile.Position;
                projectile.Delete();
            }

            if (explode)
            {
                World.AddExplosion(explosionPosition, ExplosionType.Rocket, ExplosionPower);
            }

            activeProjectile = null;
        }

        private Model ResolvePropModel()
        {
            if (!string.IsNullOrEmpty(loadedPropModelName))
            {
                return new Model(loadedPropModelName);
            }

            for (int i = 0; i < PropModelCandidates.Length; i++)
            {
                Model candidate = new Model(PropModelCandidates[i]);
                if (!candidate.isValid)
                {
                    continue;
                }

                loadedPropModelName = PropModelCandidates[i];
                return candidate;
            }

            return new Model(0);
        }

        private static Vector3 GetAimDirection(Ped player)
        {
            Camera camera = Game.CurrentCamera;
            if (camera != null)
            {
                return Normalize(camera.Direction, player.Direction);
            }

            return Normalize(player.Direction, Game.HeadingToDirection(0.0f));
        }

        private static bool IsPistol(Weapon weapon)
        {
            return weapon == Weapon.Handgun_Glock || weapon == Weapon.Handgun_DesertEagle;
        }

        private static Vector3 Normalize(Vector3 vector, Vector3 fallbackDirection)
        {
            float length = vector.Length();
            if (length <= 0.001f)
            {
                float fallbackLength = fallbackDirection.Length();
                if (fallbackLength <= 0.001f)
                {
                    return Game.HeadingToDirection(0.0f);
                }

                return fallbackDirection / fallbackLength;
            }

            return vector / length;
        }

        private sealed class ProjectileState
        {
            public ProjectileState(GTA.Object projectileObject, int spawnTime, Vector3 lastPosition)
            {
                Object = projectileObject;
                SpawnTime = spawnTime;
                LastPosition = lastPosition;
            }

            public GTA.Object Object { get; private set; }
            public int SpawnTime { get; private set; }
            public Vector3 LastPosition { get; set; }
        }
    }
}
