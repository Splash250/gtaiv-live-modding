using System;
using System.Collections.Generic;
using GTA;

namespace LiveModding
{
    public class PistolGasTanksScript : Script
    {
        private static readonly string[] GasTankModelCandidates =
        {
            "CJ_IND_GAS",
            "cj_ind_gas",
            "prop_gas_tank_01",
            "propane_tank"
        };

        private const int ShotCooldownMs = 140;
        private const int MinimumArmTimeMs = 150;
        private const int MaxFlightTimeMs = 4500;
        private const float SpawnDistance = 1.6f;
        private const float SpawnHeightOffset = 0.15f;
        private const float LaunchSpeed = 32.0f;
        private const float ImpactSpeedThreshold = 2.5f;
        private const float ImpactMovementThreshold = 0.12f;
        private const float ExplosionPower = 8.0f;

        private readonly List<GasTankProjectile> activeProjectiles = new List<GasTankProjectile>();
        private string loadedGasTankModelName;
        private bool missingModelReported;
        private int nextAllowedShotTime;

        public PistolGasTanksScript()
        {
            Interval = 0;
            Tick += new EventHandler(OnTick);
            Game.DisplayText("Pistol gas tanks loaded.", 3000);
        }

        private void OnTick(object sender, EventArgs e)
        {
            UpdateProjectiles();

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

            LaunchGasTank(player);
            nextAllowedShotTime = Game.GameTime + ShotCooldownMs;
        }

        private void LaunchGasTank(Ped player)
        {
            Model gasTankModel = ResolveGasTankModel();
            if (!gasTankModel.isValid)
            {
                if (!missingModelReported)
                {
                    Game.DisplayText("No gas tank model found for pistol launcher.", 3000);
                    missingModelReported = true;
                }

                return;
            }

            Vector3 aimDirection = GetAimDirection(player);
            Vector3 spawnPosition = player.Position + (aimDirection * SpawnDistance);
            spawnPosition.Z += SpawnHeightOffset;

            GTA.Object gasTank = World.CreateObject(gasTankModel, spawnPosition);
            if (gasTank == null)
            {
                return;
            }

            gasTank.Collision = true;
            gasTank.Heading = aimDirection.ToHeading();
            gasTank.Velocity = (aimDirection * LaunchSpeed) + player.Velocity;

            activeProjectiles.Add(new GasTankProjectile(gasTank, Game.GameTime, gasTank.Position));
            gasTank.NoLongerNeeded();
        }

        private void UpdateProjectiles()
        {
            for (int i = activeProjectiles.Count - 1; i >= 0; i--)
            {
                GasTankProjectile projectile = activeProjectiles[i];
                if (projectile.Object == null || !projectile.Object.Exists())
                {
                    activeProjectiles.RemoveAt(i);
                    continue;
                }

                int age = Game.GameTime - projectile.SpawnTime;
                Vector3 currentPosition = projectile.Object.Position;
                float movementSinceLastTick = (currentPosition - projectile.LastPosition).Length();
                float currentSpeed = projectile.Object.Velocity.Length();

                if (age >= MaxFlightTimeMs)
                {
                    DetonateProjectile(i, currentPosition);
                    continue;
                }

                if (age >= MinimumArmTimeMs &&
                    (currentSpeed <= ImpactSpeedThreshold || movementSinceLastTick <= ImpactMovementThreshold))
                {
                    DetonateProjectile(i, currentPosition);
                    continue;
                }

                projectile.LastPosition = currentPosition;
            }
        }

        private void DetonateProjectile(int index, Vector3 explosionPosition)
        {
            GasTankProjectile projectile = activeProjectiles[index];
            if (projectile.Object != null && projectile.Object.Exists())
            {
                projectile.Object.Delete();
            }

            World.AddExplosion(explosionPosition, ExplosionType.Rocket, ExplosionPower);
            activeProjectiles.RemoveAt(index);
        }

        private Model ResolveGasTankModel()
        {
            if (!string.IsNullOrEmpty(loadedGasTankModelName))
            {
                return new Model(loadedGasTankModelName);
            }

            for (int i = 0; i < GasTankModelCandidates.Length; i++)
            {
                Model candidate = new Model(GasTankModelCandidates[i]);
                if (!candidate.isValid)
                {
                    continue;
                }

                loadedGasTankModelName = GasTankModelCandidates[i];
                return candidate;
            }

            return new Model(0);
        }

        private static Vector3 GetAimDirection(Ped player)
        {
            Camera camera = Game.CurrentCamera;
            if (camera != null)
            {
                Vector3 cameraDirection = Normalize(camera.Direction, player.Direction);
                if (cameraDirection.Length() > 0.001f)
                {
                    return cameraDirection;
                }
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

        private sealed class GasTankProjectile
        {
            public GasTankProjectile(GTA.Object projectileObject, int spawnTime, Vector3 lastPosition)
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
